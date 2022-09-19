import requests
import bs4
import sqlite3
import telebot
from telebot import types
from config import *

bot = telebot.TeleBot(TOKEN)

score = 0
q_number = 1
right_answer = None


@bot.message_handler(commands=['start'])
def start(message):
    kb_menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb_test = types.KeyboardButton('Пройти тест')
    kb_translation1 = types.KeyboardButton('Перевод eng-rus')
    kb_translation2 = types.KeyboardButton('Перевод rus-eng')
    kb_menu.add(kb_test, kb_translation1, kb_translation2)
    bot.send_message(message.chat.id, 'Привет, я English-бот! Помогаю проверить ваш уровень английского языка,'
                                      ' и умею переводить слова с английского на русский и обратно! '
                                      'Выберите нужное вам действие в меню',
                     reply_markup=kb_menu)


@bot.message_handler(content_types=['text'])
def func(message):
    global q_number

    if message.text == 'Перевод eng-rus':
        msg = bot.send_message(message.chat.id, 'Введите слово для перевода')
        bot.register_next_step_handler(msg, get_translation_eng)

    elif message.text == 'Перевод rus-eng':
        msg = bot.send_message(message.chat.id, 'Введите слово для перевода')
        bot.register_next_step_handler(msg, get_translation_rus)

    elif message.text == 'Пройти тест':
        with sqlite3.connect('data_base.db') as con:
            cur = con.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS users(
                                                                    id INTEGER,
                                                                    name TEXT,
                                                                    score INTEGER,
                                                                    user_q_number INTEGER
                                                                    )""")

            # удаление данных пользователя, если он уже проходил тест
            try:
                cur.execute("""DELETE FROM users WHERE id == (?) """,
                            (message.chat.id,))
            except sqlite3.OperationalError:
                pass

            # записываем айди, имя, счет = 0, номер вопроса = 1
            cur.execute("""INSERT INTO users(id, name, score, user_q_number) VALUES(?,?,0,1) """,
            (message.from_user.id, message.from_user.first_name,))

        test(message, 1)


def test(message, i):
    global right_answer, q_number
    with sqlite3.connect('data_base.db') as con:
        cur = con.cursor()
        cur.execute("""SELECT * FROM test WHERE id == (?)""", (i,))
        result = cur.fetchall()
        question = f'{result[0][5]}/25 {result[0][0]}'
        answer1 = result[0][1]
        answer2 = result[0][2]
        answer3 = result[0][3]
        answer4 = result[0][4]

        # Кнопки под вопросом
        kb_answers = types.InlineKeyboardMarkup()
        kb_answer1 = types.InlineKeyboardButton(text=answer1, callback_data= 1)
        kb_answer2 = types.InlineKeyboardButton(text=answer2, callback_data= 2)
        kb_answer3 = types.InlineKeyboardButton(text=answer3, callback_data= 3)
        kb_answer4 = types.InlineKeyboardButton(text=answer4, callback_data= 4)
        kb_answers.row(kb_answer1, kb_answer2)
        kb_answers.row(kb_answer3, kb_answer4)
        bot.send_message(message.chat.id, question, reply_markup=kb_answers)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    global right_answer, q_number, score

    # сообщение без кнопок
    bot.edit_message_text(call.message.text, call.message.chat.id, call.message.id)

    with sqlite3.connect('data_base.db') as con:
        cur = con.cursor()

        # берем из базы данных баллы и номер вопроса пользователя
        cur.execute("""SELECT * FROM users WHERE id == (?)""", (call.message.chat.id,))
        res = cur.fetchall()
        score = res[0][2]
        q_number = res[0][3]

        # берем из базы данных правильный ответ
        cur.execute("""SELECT * FROM test WHERE id == (?)""", (q_number,))
        result = cur.fetchall()
        right_answer = result[0][6]

    # прибавили балл если пользователь ответил правильно
    if call.data == str(right_answer):
        score += 1

    q_number += 1

    with sqlite3.connect('data_base.db') as con:
        cur = con.cursor()

        # обновление баллов пользователя и номера вопроса
        cur.execute("""UPDATE users SET score = (?) WHERE id == (?)""",
                    (score, call.message.chat.id,))
        cur.execute("""UPDATE users SET user_q_number = (?) WHERE id == (?)""",
                    (q_number, call.message.chat.id,))

    if q_number <= 25: # продолжаем тест
        test(call.message, q_number)

    else: # выводим результат
        if 0 <= score <= 7:
            bot.send_message(call.message.chat.id, f'У вас {score} правильных ответов! Beginner-level')

        elif 8 <= score <= 12:
            bot.send_message(call.message.chat.id, f'У вас {score} правильных ответов! Elementary-level')

        elif 13 <= score <= 17:
            bot.send_message(call.message.chat.id, f'У вас {score} правильных ответов! PreIntermediate-level')

        elif 18 <= score <= 22:
            bot.send_message(call.message.chat.id, f'У вас {score} правильных ответов! Intermediate-level')

        elif 23 <= score <= 25:
            bot.send_message(call.message.chat.id, f'У вас {score} правильных ответов! Advanced-level')

        bot.send_message(call.message.chat.id, 'Выберите следующее действие в меню')

    score = 0
    q_number = 1


def get_translation_eng(message):
    word = message.text
    url = f'https://www.translate.ru/%D0%BF%D0%B5%D1%80%D0%B5%D0%B2%D0%BE%D0%B4/%D0%B0%D0%BD%D0%B3%D0%BB%D0%B8%D0%B9%D1%81%D0%BA%D0%B8%D0%B9-%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9/{word}'
    r = requests.get(url)

    soup = bs4.BeautifulSoup(r.text, 'html.parser')
    translation = soup.select('span.result_only.sayWord')

    clear_list = []
    for i in translation:
        clear_list.append(i.getText())

    sense = ', '.join(clear_list)
    if not sense:
        sense = 'Ничего не найдено'
    bot.send_message(message.chat.id, sense)  # Высылает перевод введенного слова
    bot.send_message(message.chat.id, 'Выберите следующее действие в меню')


def get_translation_rus(message):
    word = message.text
    url = f'https://www.translate.ru/%D0%BF%D0%B5%D1%80%D0%B5%D0%B2%D0%BE%D0%B4/%D1%80%D1%83%D1%81%D1%81%D0%BA%D0%B8%D0%B9-%D0%B0%D0%BD%D0%B3%D0%BB%D0%B8%D0%B9%D1%81%D0%BA%D0%B8%D0%B9/{word}'
    r = requests.get(url)

    soup = bs4.BeautifulSoup(r.text, 'html.parser')
    translation = soup.select('span.result_only.sayWord')

    clear_list = []
    for i in translation:
        clear_list.append(i.getText())

    sense = ', '.join(clear_list)
    if not sense:
        sense = 'Ничего не найдено'
    bot.send_message(message.chat.id, sense)  # Высылает перевод введенного слова
    bot.send_message(message.chat.id, 'Выберите следующее действие в меню')


bot.polling(none_stop=True)
