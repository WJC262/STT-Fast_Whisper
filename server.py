import asyncio # 导入 asyncio 库以使用异步功能
import logging # 导入 logging 用于记录日志
import time
from collections import deque

import aioredis # 导入 aioredis 以使用异步 Redis 客户端
from faster_whisper import WhisperModel

from .config import REDIS_SERVER
from .utils import asyncformer

CONVERSATION = deque(maxlen=100)
MODEL_SIZE = "large-v3"
CN_PROMPT = '聊一下基于faster-whisper的实时/低延迟语音转写服务'
logging.basicConfig(level=logging.INFO)
model = WhisperModel(MODEL_SIZE, device="auto", compute_type="default")#加载模型
logging.info('Model loaded')


async def transcribe():   # 异步函数，用于从 Redis 队列中获取音频数据并进行转录
    # download audio from redis by popping from list: STS:AUDIO
    def b_transcribe():  # 内部函数，用于同步转录音频到文本
        # transcribe audio to text
        start_time = time.time()
        segments, info = model.transcribe("chunk.mp3",
                                          beam_size=5,
                                          initial_prompt=CN_PROMPT) # 调用模型的转录函数，将音频文件 "chunk.mp3" 转录为文本
        end_time = time.time()
        period = end_time - start_time
        text = ''  # 初始化存储转录文本的字符串
        for segment in segments: # 遍历转录的段落，拼接成一个完整的文本
            t = segment.text
            if t.strip().replace('.', ''):
                text += ', ' + t if text else t
        return text, period # 返回转录文本和时间

    async with aioredis.from_url(REDIS_SERVER) as redis: # 异步连接到 Redis 服务器
        '-' * 81
        while True:
            length = await redis.llen('STS:AUDIOS')  # 获取队列中音频文件的数量
            if length > 10:
                await redis.expire('STS:AUDIOS', 1) # 如果队列长度超过 10，设置队列过期时间为 1 秒
            content = await redis.blpop('STS:AUDIOS', timeout=0.1) # 从队列中弹出一个音频文件，设置超时时间为 0.1 秒
            if content is None: # 如果队列为空，则继续等待
                continue

            with open('chunk.mp3', 'wb') as f:# 将弹出的音频文件写入本地文件 "chunk.mp3"
                f.write(content[1])

            text, _period = await asyncformer(b_transcribe)# 异步调用 b_transcribe 函数进行转录
            t = text.strip().replace('.', '')# 去除文本中的句号并
            logging.info(t)#记录日志
            CONVERSATION.append(text)


async def main():
    await asyncio.gather(transcribe())


if __name__ == '__main__':
    asyncio.run(main())
