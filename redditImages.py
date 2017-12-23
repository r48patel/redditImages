#!/usr/bin/env python2.7
from multiprocessing import Process, Queue, current_process, freeze_support
import time
import random
import sys
import requests
import argparse
import os
import progressbar
import logging
import datetime

FORMAT = '[%(levelname)s %(funcName)s (%(processName)s)] - %(message)s'
logging.basicConfig(format=FORMAT)
level = None


class subReddit:
    def __init__(self, url, process_count, location, pages):
        self.url = url
        self.queue = Queue()
        self.process_count = process_count
        self.location = location
        self.pages = pages
        self.sub = url.split('/')[-2]

        self.logger = logging.getLogger('reddigImages')
        self.logger.setLevel(level)
        hdlr = logging.FileHandler('{}/{}_{}.log'.format(location, self.sub, datetime.datetime.now().strftime('%Y%m%d_%H%M%S')))
        hdlr.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(hdlr)

        self.add_process = Process(target=add_pages, args=(self.logger, self.url,self.queue,self.pages,))
        self.add_process.name = 'Add Pages'
        self.add_process.daemon = True
        self.add_process.start()

        self.logger.info('Download for %s started!' % url)

        time.sleep(5)
        self.logger.debug('queue empty: %s' % self.queue.empty())

        self.jobs = []
        for i in range(0, process_count):
            job = Process(target=get_data, args=(self.logger, self.url, self.queue,self.location,))
            job.daemon = True
            job.name = '%s_imgProcess_%s' % (self.sub, i)
            self.jobs.append(job)
            try:
                job.start()
            except OSError, e:
                logger.info( 'Can\'t start process %s because of %s' % (i, str(e)))



    def alive(self):
        self.logger.debug('Checking if %s processes are alive!' % self.sub)
        self.logger.debug('add_process_alive: %s' % self.add_process.is_alive())
        self.logger.debug('queue_empty: %s' % self.queue.empty())
        if self.queue.empty():
            if not self.add_process.is_alive():
                for job in self.jobs:
                    self.logger.debug('terminating: %s' % job.name)
                    job.terminate()
                    self.logger.debug('terminated: %s' % job.name)
                    self.logger.debug('Waiting for it to join: %s' % job.name)
                    job.join(10)
                    self.logger.debug('joined: %s' % job.name)
                return False
        return True

def add_pages(log, url, queue, MAX):
    counter = 0
    after = ''
    while counter < MAX or MAX == 0:
        while True:
            r = requests.get(url, headers = {'User-agent': 'redditImages v0.1'}, params={'after': after})
            if r.status_code == 200:
                break
            else:
                log.info('Waiting before retrying.')
                time.sleep(10)
        log.debug('status code: %s' % r.status_code)
        value = r.json()
        queue.put(value)
        if value['kind'] == 'Listing' and 'after' in value['data'].keys():
            after = value['data']['after']
        else:
            break
        counter += 1
    return

def get_data(log, url, queue, location):
    log.debug('Starting to download for %s' % url)
    while True:
        if queue.empty():
            return

        post = queue.get()
        kind = post['kind']

        if kind == 'Listing':
            for child in post['data']['children']:
                queue.put(child)
            get_data(log, url,queue,location)
        elif kind in ['t1', 't3']:
            post=post['data']
            post_name = post['title']
            post_url = ''
            try:
                if 'gallery' in post['url']:
                    pic_name = download_imgur_image(log, post['url'], location)
                else:
                    post_images_data = post['preview']['images'][0]
                    if kind == 't3':
                        post_url = post_images_data['source']['url'] if len(post_images_data['variants']) == 0 else post_images_data['variants']['gif']['source']['url']
                    elif kind == 't1':
                        post_url = post['link_url']
                    pic_name = download_images(log, post_url, location)
            except KeyError:
                log.info( 'Post with title: \'%s\' does not have a picture' % post_name)
            log.info('%s - %s' % (post_name, pic_name))
        else:
            log.info( 'This kind "%s" is not supported atm' % post['kind'])

def download_imgur_image(log, url, location, local_filename=None):
    results = []
    r = requests.get(url+'.json')
    if r.status_code != 200:
        log.info( 'Can\'t download: %s' % url)
        return result
    value = r.json()
    album_info = value['data']['image']['album_images']

    for i in range(0, album_info['count']):
        name = album_info['images'][i]['hash']
        ext = album_info['images'][i]['ext']
        url = 'https://i.imgur.com/{}{}'.format(name, ext)
        results.append(download_images(url, location, local_filename))

    return results

def download_images(log, url, location, local_filename=None):
    if not local_filename:
        local_filename = url.split('/')[-1].split('?')[0]

    logger.debug( 'downloading %s' % local_filename)

    if not os.path.isfile(os.path.join(location, local_filename)):
        r = requests.get(url, stream=True)
        with open(os.path.join(location, local_filename), 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)

    return local_filename

if __name__ == '__main__':
    parser = argparse.ArgumentParser('redditImages')
    parser.add_argument('--subreddits', '-r', nargs='+', required=True)
    parser.add_argument('--total-pages', '-p', type=int, default=1)
    parser.add_argument('--total-threads', '-t', type=int, default=1)
    parser.add_argument('--type', default='new', choices=['hot', 'new', 'rising', 'controversial', 'top',  'gilded'])
    parser.add_argument('--download-location', default=os.getcwd())
    parser.add_argument('--verbose', '-v', default=False, action='store_true' )

    args = parser.parse_args()
    processes = args.total_threads
    jobs = []
    completed_jobs = []
    bar = progressbar.ProgressBar(max_value=progressbar.UnknownLength,redirect_stdout=True)
    bar.update(0)

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG

    logger = logging.getLogger('reddigImages')
    logger.setLevel(level)

    try:
        for subreddit in args.subreddits:
            results = []
            url = 'https://www.reddit.com/r/{}/{}.json'.format(subreddit, args.type)

            location = os.path.join(args.download_location, 'images','r','{}'.format(subreddit))
            if not os.path.exists(location):
                os.makedirs(location)

            sub = subReddit(url, processes, location, args.total_pages)
            jobs.append(sub)
            logger.info('Location: %s' % location)


        logger.info('Waiting for process to finish ')
        counter = 1
        while True:
            if len(jobs) == len(completed_jobs):
                break
            else:
                for job in jobs:
                    if not job.alive():
                        completed_jobs.append(job)

            bar.update(counter)
            time.sleep(2)
            counter += 1

    except Exception, e:
        logger.error('Failed to upload to ftp: '+ str(e))

