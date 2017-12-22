#!/usr/bin/env python2.7
from multiprocessing import Process, Queue, current_process, freeze_support
import time
import random
import sys
import requests
import argparse
import os
import progressbar

class subReddit:
    def __init__(self, url, process_count, location, pages):
        self.url = url
        self.queue = Queue()
        self.process_count = process_count
        self.location = location
        self.pages = pages
        
        self.add_process = Process(target=add_pages, args=(self.url,self.queue,self.pages,))
        self.add_process.name = 'Add Pages'
        self.add_process.daemon = True
        self.add_process.start()

        print 'Download for \'',url,'\' started!'

        time.sleep(10)
        # print 'queue empty: ', self.queue.empty()
        self.jobs = []
        for i in range(0, process_count):
            job = Process(target=get_data, args=(self.url, self.queue,self.location,))
            job.daemon = True
            job.name = 'images_process_%s' % i
            self.jobs.append(job)
            try:
                job.start()
            except OSError, e:
                print 'Can\'t start process %s because of %s' %(i, str(e))



    def alive(self):
        # print 'Checking if alive'
        # print 'add_process_alive: ', self.add_process.is_alive()
        # print 'queue_empty: ', self.queue.empty()
        if self.queue.empty():
            if not self.add_process.is_alive():
                for job in self.jobs:
                    # print 'terminating: ', job.name
                    job.terminate()
                    # print 'Waiting for it to join: ', job.name
                    job.join()
                return False
        return True

def add_pages(url, queue, MAX):
    counter = 0
    after = ''
    while counter < MAX or MAX == 0:
        # print counter
        while True:
            r = requests.get(url, headers = {'User-agent': 'redditImages v0.1'}, params={'after': after})
            if r.status_code == 200:
                break
            else:
                print 'Waiting before retrying.'
                time.sleep(10)
        # print r.status_code
        value = r.json()
        queue.put(value)
        if value['kind'] == 'Listing' and 'after' in value['data'].keys():
            after = value['data']['after']
        else:
            break
        counter += 1
    return

def get_pages(queue,num):
    while True:
        print 'Process #%s Sub: %s' % (num, queue.get().keys())
        if queue.empty():
            break

        time.sleep(1)
    return

def get_data(url, queue, location):
    # print 'Starting to download for ', url
    while True:
        if queue.empty():
            return

        post = queue.get()
        kind = post['kind']

        if kind == 'Listing':
            for child in post['data']['children']:
                queue.put(child)
            get_data(url,queue,location)
        elif kind in ['t1', 't3']:
            post=post['data']
            post_name = post['title']
            post_url = ''
            try:
                if 'gallery' in post['url']:
                    download_imgur_image(post['url'], location)
                else:
                    post_images_data = post['preview']['images'][0]
                    if kind == 't3':
                        post_url = post_images_data['source']['url'] if len(post_images_data['variants']) == 0 else post_images_data['variants']['gif']['source']['url']
                    elif kind == 't1':
                        post_url = post['link_url']
                    download_images(post_url, location)
            except KeyError:
                print 'Post with title: \'%s\' does not have a picture' % post_name
            # get_images(post['data'], post['kind'], location)
        else:
            print 'This kind "%s" is not supported atm' % post['kind']


def download_imgur_image(url, location, local_filename=None):
    results = []
    r = requests.get(url+'.json')
    if r.status_code != 200:
        print 'Can\'t download: ', url
        return result
    value = r.json()
    album_info = value['data']['image']['album_images']
    
    for i in range(0, album_info['count']):
        name = album_info['images'][i]['hash']
        ext = album_info['images'][i]['ext']
        url = 'https://i.imgur.com/{}{}'.format(name, ext)
        results.append(download_images(url, location, local_filename))


def download_images(url, location, local_filename=None):
    print 'downloading ', url
    if not local_filename:
        local_filename = url.split('/')[-1].split('?')[0]
    if not os.path.isfile(os.path.join(location, local_filename)):
        r = requests.get(url, stream=True)
        with open(os.path.join(location, local_filename), 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)

if __name__ == '__main__':
    parser = argparse.ArgumentParser('redditImages')
    parser.add_argument('--subreddits', '-r', nargs='+', required=True)
    parser.add_argument('--total-pages', '-p', type=int, default=1)
    parser.add_argument('--total-threads', '-t', type=int, default=1)
    parser.add_argument('--type', default='new', choices=['hot', 'new', 'rising', 'controversial', 'top',  'gilded'])
    parser.add_argument('--download-location', default=os.getcwd())

    args = parser.parse_args()
    processes = args.total_threads
    jobs = []
    completed_jobs = []
    bar = progressbar.ProgressBar(max_value=progressbar.UnknownLength,redirect_stdout=True)
    bar.update(0)

    for subreddit in args.subreddits:
        results = []
        url = 'https://www.reddit.com/r/{}/{}.json'.format(subreddit, args.type)
        
        location = os.path.join(args.download_location, 'images','r','{}'.format(subreddit))
        if not os.path.exists(location):
            os.makedirs(location)
        

        sub = subReddit(url, processes, location, args.total_pages)
        jobs.append(sub)
        print 'Location: %s' % location


    print 'Waiting for process to finish '
    counter = 1
    while True:
        if len(jobs) == len(completed_jobs):
            break
        else:
            for job in jobs:
                # print 'job: %s is_alive(): %s' % (job, job.alive())
                if not job.alive():
                    completed_jobs.append(job)
        
        bar.update(counter)
        time.sleep(2)
        counter += 1









