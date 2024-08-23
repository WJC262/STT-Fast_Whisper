import os

from dotenv import load_dotenv

load_dotenv()
REDIS_SERVER = os.getenv('redis://redis-10834.c54.ap-northeast-1-2.ec2.redns.redis-cloud.com:10834/0')

if REDIS_SERVER is None:
    raise EnvironmentError(
        "The REDIS_SERVER environment variable is not set. "
        "Please set it in your .env file or as an environment variable.")
