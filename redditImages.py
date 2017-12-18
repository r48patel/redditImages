#!/usr/bin/env python2.7
import requests
from prettytable import PrettyTable
import os
import argparse


def download_images(url, location, local_filename=None):
	if not local_filename:
		local_filename = url.split('/')[-1].split('?')[0]
	if not os.path.isfile(os.path.join(location, local_filename)):
		r = requests.get(url, stream=True)
		with open(os.path.join(location, local_filename), 'wb') as f:
			for chunk in r.iter_content(chunk_size=1024):
				if chunk: # filter out keep-alive new chunks
					f.write(chunk)
	return local_filename

def get_images(post, kind, location):
	post_name = post['title']
	post_images_data = post['preview']['images'][0]
	post_url = ''
	try:
		if kind == 't3':
			post_url = post_images_data['source']['url'] if len(post_images_data['variants']) == 0 else post_images_data['variants']['gif']['source']['url']
		elif kind == 't1':
			post_url = post['link_url']
		return {post_name: download_images(post_url, location)}
	except KeyError:
		print 'Post with title: \'%s\' does not have a picture' % post_name
		return {post_name:'N/A'}

def get_data(post, location):
	results = []
	if post['kind'] == 'Listing':
		for child in post['data']['children']:
			results += get_data(child, location)
	elif post['kind'] in ['t1', 't3']:
		results.append(get_images(post['data'], post['kind'], location))
	else:
		print 'This kind "%s" is not supported atm' % post['kind']
	return results

def get_pages(url, MAX=2, after=''):
	returned_json = []
	counter = 0
	while counter < MAX or MAX == 0:
		r = requests.get(url, headers = {'User-agent': 'redditImages v0.1'}, params={'after': after})
		value = r.json()
		returned_json.append(value)
		if value['kind'] == 'Listing':
			after = value['data']['after']
		else:
			break
		counter += 1

	return returned_json

if __name__== '__main__':
	parser = argparse.ArgumentParser('redditImages')
	parser.add_argument('--subreddits', '-r', nargs='+', required=True)
	parser.add_argument('--total-pages', type=int, default=1)
	parser.add_argument('--type', default='new', choices=['hot', 'new', 'rising', 'controversial', 'top',  'gilded'])
	parser.add_argument('--download-location', default=os.getcwd())

	args = parser.parse_args()

	for subreddit in args.subreddits:
		results = []
		url = 'https://www.reddit.com/r/{}/{}.json'.format(subreddit, args.type)
		table = PrettyTable(['Sub', 'Post', 'Image Link'])
		location = os.path.join(args.download_location, 'images','r','{}'.format(subreddit))
		if not os.path.exists(location):
			os.makedirs(location)
		
		returned_json = get_pages(url, args.total_pages)

		for item in returned_json:
			results+=get_data(item, location)

		for result in results:
			table.add_row([subreddit, result.keys()[0], result[result.keys()[0]]])
			table.add_row([subreddit, "", ""])

		print 'Location: %s' % location
		print table







