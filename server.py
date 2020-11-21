import os
import asyncio
import aiofiles
import argparse
import logging

from aiohttp import web
from dotenv import load_dotenv


BYTES_READ_AT_ONE_TIME = 102400


async def archivate(request):
    archive_hash = request.match_info.get('archive_hash')
    path_to_files = f'{path_to_catalog_with_photos}/{archive_hash}'
    if not os.path.exists(path_to_files):
        raise web.HTTPFound('/404.html/')

    process = await asyncio.create_subprocess_exec(
        *f'zip -rjq - {path_to_files} | cat'.split(' '),
        stdout=asyncio.subprocess.PIPE
    )

    response = web.StreamResponse()
    response.headers['Content-Type'] = 'multipart/form-data'
    response.headers['Content-Disposition'] = f'filename="{archive_hash}.zip"'

    await response.prepare(request)

    try:

        while True:
            logging.debug(u'Sending archive chunk')
            stdout = await process.stdout.read(n=BYTES_READ_AT_ONE_TIME)
            await response.write(stdout)
            if process.stdout.at_eof():
                await response.write_eof()
                break
            await asyncio.sleep(response_delay_time)

    except asyncio.CancelledError:
        logging.debug(u'Download was interrupted')
        raise

    except RuntimeError:
        logging.debug(u'Download was сanceled')
        process.communicate()

    finally:
        process.kill()

    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


async def handle_404_page(request):
    async with aiofiles.open('404.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


def create_parser():
    parser = argparse.ArgumentParser(description='Параметры запуска скрипта')
    parser.add_argument('-p', '--photos', default='test_photos', help='Путь к каталогу с фотографиями')
    return parser


if __name__ == '__main__':

    args = create_parser().parse_args()
    path_to_catalog_with_photos = args.photos

    load_dotenv()
    response_delay_time = int(os.environ['RESPONSE_DELAY'])

    if int(os.environ['ENABLE_LOGGING']):
        logging.basicConfig(level=logging.DEBUG)

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archivate),
        web.get('/404.html/', handle_404_page),
    ])
    web.run_app(app)
