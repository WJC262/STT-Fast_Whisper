import asyncio
import collections
import wave
from collections import deque

import aioredis
import pyaudio
import webrtcvad
import logging
#from .utils import asyncformer
#from .config import REDIS_SERVER

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any


async def asyncformer(sync_func: Callable, *args, **kwargs) -> Any:
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, sync_func, *args, **kwargs)

import os

from dotenv import load_dotenv

load_dotenv()
#REDIS_SERVER = os.getenv('redis://localhost:6379/0')
REDIS_SERVER ='redis://default:bqIdEXBsQJKACzSTKccWA2nl6GUIwnL0@redis-10834.c54.ap-northeast-1-2.ec2.redns.redis-cloud.com:10834/0'

if REDIS_SERVER is None:
    raise EnvironmentError(
        "The REDIS_SERVER environment variable is not set. "
        "Please set it in your .env file or as an environment variable.")


# Audio recording parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 256
FRAME_DURATION = 30  # 毫秒
FRAME_SIZE = int(RATE * FRAME_DURATION / 1000)

g_frames = deque(maxlen=100)
audio = pyaudio.PyAudio()
logging.basicConfig(level=logging.INFO)

# for audio recording
stream = audio.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)


async def sync_audio():
    # Sync audio to redis server list STS:AUDIO
    async with aioredis.from_url(REDIS_SERVER) as redis:
        while True:
            if g_frames:
                content = g_frames.pop()
                await redis.rpush('STS:AUDIOS', content)
                logging.info('Sync audio to redis server')


def export_wav(data, filename):
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(data))
    wf.close()


def record_until_silence():
    frames = collections.deque(maxlen=30)  # 保存最近 30 个帧
    tmp = collections.deque(maxlen=1000)
    vad = webrtcvad.Vad()
    vad.set_mode(1)  # 敏感度，0 到 3，0 最不敏感，3 最敏感
    triggered = False
    frames.clear()
    ratio = 0.5
    while True:
        frame = stream.read(FRAME_SIZE)
        is_speech = vad.is_speech(frame, RATE)
        if not triggered:
            frames.append((frame, is_speech))
            tmp.append(frame)
            num_voiced = len([f for f, speech in frames if speech])
            if num_voiced > ratio * frames.maxlen:
                logging.info("开始录制...")
                triggered = True
                frames.clear()
        else:
            frames.append((frame, is_speech))
            tmp.append(frame)
            num_unvoiced = len([f for f, speech in frames if not speech])
            if num_unvoiced > ratio * frames.maxlen:
                logging.info("结束录制...")
                export_wav(tmp, 'output.wav')
                with open('output.wav', 'rb') as f:
                    g_frames.appendleft(f.read())
                break


async def record_audio():
    while True:
        await asyncformer(record_until_silence)


async def main():
    try:
        task2 = asyncio.create_task(record_audio())
        task3 = asyncio.create_task(sync_audio())
        await asyncio.gather(task2, task3)
    except KeyboardInterrupt:
        stream.stop_stream()
        stream.close()
        audio.terminate()


def api():
    return asyncio.run(main())


if __name__ == "__main__":
    import fire
    fire.Fire(api)
