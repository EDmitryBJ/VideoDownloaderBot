import asyncio
import re
import time

import aiohttp
from aiogram import types, Dispatcher
from create_bot import bot
from bs4 import BeautifulSoup
from pytube import YouTube


async def command_start(message: types.Message):
    try:
        await message.delete()
        await bot.send_message(message.from_user.id,
                               "Введите ссылку на плейлист и бот вышлет ссылки на скачивание всех "
                               "содержащихся в нём видео.\nФормат ввода: \n<ссылка на видео/плейлист/канал>"
                               " <разрешение в формате: 720p.>")
    except:
        await message.reply("Команды боту возможны только через ЛС")


async def send_requests(yt, resolution):
    name = await yt.title
    link = await yt.streams
    link = link.filter(res=resolution).first().url
    return name, link


async def get_video_link(link, resolution):
    url = link
    yt = YouTube(link)
    name = None
    link = None
    counter = 0
    while name is None and counter < 15:
        counter += 1
        try:
            print("requests {}".format(counter))
            name, link = await send_requests(yt, resolution)
        except:
            name = None
            link = None
    if counter == 10:
        name = "Ошибка получения названия"
        link = "Ошибка получения ссылки"
    else:
        print("request successful")
    return name, link


async def scrape_lists(url, session):
    async with session.get(url) as resp:
        send = BeautifulSoup(await resp.text(), "lxml")
        search = send.find_all("script")
        key = '"playlistId":"'
        data = re.findall(key + r"([^*]{34})", str(search))
        data = data[::3]
        return data


async def scrape_videos(url, session):
    async with session.get(url) as resp:
        bs = BeautifulSoup(await resp.text(), 'lxml')
        search = bs.find_all("script")
        key = '"videoId":"'
        data = re.findall(key + r"([^*]{11})", str(search))
        data = data[::3]
        data = data[:-2]
        return data


async def prepare_data(vid_ids, resolution, bot, message):
    tasks = [asyncio.create_task(get_video_link(str("https://www.youtube.com/watch?v=" + vid_id), resolution))
             for vid_id in vid_ids]
    names_links = await asyncio.gather(*tasks)
    await bot.send_message(message.from_user.id, "Ваши видео:")
    for pare in names_links:
        await bot.send_message(message.from_user.id, "{}: {}".format(pare[0], pare[1]))


async def link_handler(message: types.Message):
    connector = aiohttp.TCPConnector(force_close=True, limit=0)
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            msg_parts = message.text.split(' ')
            url = msg_parts[0]
            resolution = msg_parts[1]
        except:
            await bot.send_message(message.from_user.id,
                                   "Неправильный ввод.\nФормат ввода:\n<ссылка на видео/плейлист/канал>"
                                   " <разрешение в формате: 720p.>")
            return
        try:
            if url.__contains__("/c/"):
                temp_msg = await bot.send_message(message.from_user.id, "Собираю видео из плейлистов канала")
                arr_url = url.split("/")
                if len(arr_url) > 5 and not url.__contains__("playlists"):
                    arr_url[-1] = "playlists"
                    url = "/".join(arr_url)
                else:
                    url += "/playlists"
                playlists = await scrape_lists(url, session)
                vid_ids = []
                for playlist_id in playlists:
                    vid_ids.extend(await scrape_videos(
                        "https://www.youtube.com/playlist?list={}".format(playlist_id),
                        session))
                tasks = [asyncio.create_task(
                    get_video_link(str("https://www.youtube.com/watch?v=" + vid_id), resolution))
                    for vid_id in vid_ids]
            elif url.__contains__("playlist"):
                temp_msg = await bot.send_message(message.from_user.id, "Собираю видео из плейлиста")
                vid_ids = await scrape_videos(url, session)
                tasks = [asyncio.create_task(
                    get_video_link(str("https://www.youtube.com/watch?v=" + vid_id), resolution))
                    for vid_id in vid_ids]
            else:
                temp_msg = await bot.send_message(message.from_user.id, "Обрабатываю данные видео")
                vid_id = url.split('/')[-1]
                tasks = [asyncio.create_task(
                    get_video_link(str("https://www.youtube.com/watch?v=" + vid_id), resolution))]
        except Exception as e:
            await bot.send_message(message.from_user.id,
                                   "Неправильный ввод.\nФормат ввода:<https://...> <.../720p/480p/...>")
            return
        t0 = time.time()
        names_links = await asyncio.gather(*tasks)
        print("{} tasks take {} sec".format(len(tasks), time.time() - t0))
        await temp_msg.delete()
        await bot.send_message(message.from_user.id, "Ваши видео:")
        for pare in names_links:
            await bot.send_message(message.from_user.id, "{}: {}".format(pare[0], pare[1]))


def register_handlers_client(dp: Dispatcher):
    dp.register_message_handler(command_start, commands=['start', 'help'])
    dp.register_message_handler(link_handler)
