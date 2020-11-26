import os
import asyncio
import aiofiles
import argparse
import logging

from aiohttp import web
from dotenv import load_dotenv


BYTES_READ_AT_ONE_TIME = 102400


async def archivate(request, response_delay, path_to_photos):
    archive_hash = request.match_info['archive_hash']
    archive_path = os.path.join(path_to_photos, archive_hash)
    if not os.path.exists(archive_path):
        raise web.HTTPFound('/404.html/')

    process = await asyncio.create_subprocess_exec(
        *['zip', '-r', '-', archive_hash, '|', 'cat'],
        cwd=path_to_photos,
        stdout=asyncio.subprocess.PIPE
    )

    response = web.StreamResponse()
    response.headers['Content-Type'] = 'multipart/form-data'
    response.headers['Content-Disposition'] = f'filename="{archive_hash}.zip"'
    await response.prepare(request)

    try:

        while True:
            logging.debug(u'Sending archive chunk')
            chunk_of_archive = await process.stdout.read(n=BYTES_READ_AT_ONE_TIME)
            await response.write(chunk_of_archive)
            if process.stdout.at_eof():
                await response.write_eof()
                break
            await asyncio.sleep(response_delay)

    except asyncio.CancelledError:
        logging.debug(u'Download was interrupted')
        raise

    finally:
        process.kill()
        await process.communicate()

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


def main():
    args = create_parser().parse_args()
    path_to_photos = args.photos

    load_dotenv()
    response_delay = int(os.getenv('RESPONSE_DELAY', 0))

    if int(os.getenv('ENABLE_LOGGING', 0)):
        logging.basicConfig(level=logging.DEBUG)

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get(
            '/archive/{archive_hash}/',
            lambda request=web.Request, response_delay=response_delay, path_to_photos=path_to_photos: archivate(
                request,
                response_delay,
                path_to_photos
            )
        ),
        web.get('/404.html/', handle_404_page),
    ])
    web.run_app(app)


if __name__ == '__main__':
    main()
