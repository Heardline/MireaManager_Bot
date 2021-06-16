import os
from sqlalchemy.sql.expression import text
import config
from aiogram import types, Dispatcher
from sqlalchemy import select,insert
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import Text
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
import utils.task_manager as task_manager
from utils.db.db import Student, Group, import_from_xlsx
#Переключение пользователя

class Status(StatesGroup):  
    group_select = State()  # Статус - выбор группы
    sub = State() #Уведомление
    complete = State()
    task_name = State()
    task_change = State()  #Проверка авторизации 


async def send_welcome(message: types.Message):
    db_session = message.bot.get('db')
    sql = select(Student).where(Student.telegram_id == message.from_user.id)
    # Проверяем есть ли в базе студент
    async with db_session() as session:
        request = await session.execute(sql)
        student = request.scalar()
        if not student:
            student = Student(telegram_id=message.from_user.id)
            session.add(student)
            await session.commit()
            await Status.group_select.set()
            with open(config.FileLocation.cmd_welcome, 'r', encoding='utf-8') as file:
                await message.reply(file.read(), parse_mode='HTML', disable_web_page_preview=True)
        else:
            await message.answer(message.chat.id, "<b> Привет, рад тебя видеть снова </b>", parse_mode='HTML', disable_web_page_preview=True)
            await Status.complete.set()
            await menu(message)

# Внесение группы  
async def select_group(message: types.Message,state: FSMContext):
    db_session = message.bot.get('db')
    sql = select(Group).where(Group.name == message.text)
    async with db_session() as session:
        request = await session.execute(sql)
        group = request.scalar()
        if group:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
            markup.add("Да", "Нет")
            # Заносим группу студенту
            sql = select(Student).where(Student.telegram_id == message.from_user.id)
            request = await session.execute(sql)
            student = request.scalar()
            student.group = message.text
            await session.commit()
            with open(config.FileLocation.cmd_group,'r', encoding='utf-8') as file:
                await message.answer(file.read(), parse_mode='HTML', disable_web_page_preview=True, reply_markup=markup)
            await Group.next()
        else:
            await message.reply("Что-то пошло не так, проверь, чтобы группа была формата ГИБО-05-19. Если не получается, значит база данных не доступна либо ваша группа не загружена.", parse_mode='HTML', disable_web_page_preview=True)

# Настройка Уведомление за 20 минут
async def select_notify(message: types.Message,state: FSMContext):
    db_session = message.bot.get('db')
    async with db_session() as session:
        if message.text == "Да":
            sql = select(Student).where(Student.telegram_id == message.from_user.id)
            request = await session.execute(sql)
            student = request.scalar()
            student.notify = True
            await session.commit()
        else:
            sql = select(Student).where(Student.telegram_id == message.from_user.id)
            student = await session.execute(sql).scalar()
            student.notify = False
            await session.commit()
    markup = types.ReplyKeyboardRemove()
    await Group.complete.set()
    await menu(message)
    # Конец регистрации

# Главное меню
async def menu(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, selective=True)
    markup.add("Сегодня ⏲", "Завтра 📆", "Неделя 📅","Мои задачи 📋","Настройки 🛠")
    with open(config.FileLocation.cmd_menu,'r', encoding='utf-8') as file:
            await message.answer(file.read(), parse_mode='HTML', disable_web_page_preview=True, reply_markup=markup)

# Пары на сегодня
async def scheduler_today(message: types.Message):
    Lessons = f"<b> Пары на {time_lesson.TodayToEmoji(0)} | {time_lesson.NumberOfMonth()} неделя. </b> \n" 
    group = pdb.get_group(message.chat.id)
    check_lesson = False
    for i in range(1,7):
        if time_lesson.NumberOfMonth() % 2 == 0: # Четная/ не четная неделя
            a = i*2
        else:
            a = (i*2)-1
        if pdb.get_lesson(time_lesson.todayIs()+a,group):
            pass
        else: 
            check_lesson = True
            Lessons = pdb.ready_lesson(Lessons,group, a,i)
    if check_lesson is False:
        Lessons = "<b>Сегодня нету пар </b> ✨🎉\n Иди гуляй)"
    await message.reply(Lessons, parse_mode='HTML', disable_web_page_preview=True)

async def scheduler_tomorrow(message: types.Message):
    Lessons = f"<b> Пары на {time_lesson.TodayToEmoji(0)} | {time_lesson.NumberOfMonth()} неделя. </b> \n"
    group = pdb.get_group(message.chat.id)
    check_lesson = False
    for i in range(1,7):
        if time_lesson.NumberOfMonth() % 2 == 0: 
            a = i*2 + 12
        else:
            a = (i*2)-1 + 12
        if pdb.get_lesson(time_lesson.todayIs()+a,group):
            pass
        else: 
            check_lesson = True
            Lesson_obj = pdb.get_lesson(time_lesson.todayIs()+a,group)
            Lessons.join(f"{time_lesson.NumberToEmoji(i)} ")
    if check_lesson is False:
        Lessons = "<b>Завтра нету пар </b> ✨🎉\n Можешь спать и гулять))"
    await message.reply(Lessons, parse_mode='HTML', disable_web_page_preview=True)


async def task(message: types.Message):
    await bot.send_message(message.chat.id, '<b> 💡 Твои задачи </b>', parse_mode='HTML')
    inline_button_complete = InlineKeyboardButton('Выполнено', callback_data='task_complete')
    inline_button_delete = InlineKeyboardButton('Удалить', callback_data='task_delete')
    inline_button_change = InlineKeyboardButton('Изменить', callback_data='task_change')
    inline_task = InlineKeyboardMarkup().row(inline_button_complete,inline_button_change,inline_button_delete)
    for task in db["task"].find({"chat_id":message.chat.id}):
        await bot.send_message(message.chat.id,"<b>" + task["name"] + "</b>@ " + task["lesson"] + " @ до " + task["timetodo"] + "  " + task['status'] , parse_mode='HTML', reply_markup=inline_task)
    


async def addtask(message: types.Message, state: FSMContext):
    await TaskCreate.name_select.set()
    await message.reply("Окей, напиши короткое название задачи:")
    

async def select_name(message: types.Message,state: FSMContext):  
    async with state.proxy() as data:
        data['name'] = message.text
    await TaskCreate.lesson.set()
    await message.reply("А по какому предмету?(Советую точно написать название предмета, иначе не будет появлятся в расписании)")


async def select_lesson(message: types.Message,state: FSMContext):
    async with state.proxy() as data:
        data['lesson'] = message.text
    await message.reply("Лады, и до какого числа тебе нужно это сделать?(В формате число.месяц 3.02 21.05)")
    await TaskCreate.time.set()


async def select_lesson(message: types.Message,state: FSMContext):
    async with state.proxy() as data:
        data['timetodo'] = message.text
        await bot.send_message(message.chat.id,"Так, окей. Тебе надо сделать: " + data['name'] + " до " + data['timetodo'])
        task = task_manager.Task(data['name'],data['timetodo'],data['lesson'],message.chat.id)
        task.addtodb(db["task"])
    await state.finish()

async def update_data(message: types.Message):
    await import_from_xlsx(message)

def register_commands(dp: Dispatcher):
    '''dp.register_message_handler( , )'''
    dp.register_message_handler(send_welcome, commands="start"),
    dp.register_message_handler(select_group, state=Status.group_select),
    dp.register_message_handler(select_notify, state=Status.sub),
    dp.register_message_handler(menu, commands="menu"),
    dp.register_message_handler(scheduler_today,commands=['day']),
    dp.register_message_handler(scheduler_tomorrow,commands='tomorow'),
    dp.register_message_handler(task,commands='task'),
    dp.register_message_handler(addtask,commands='addtask'),
    dp.register_message_handler(update_data,commands='update')