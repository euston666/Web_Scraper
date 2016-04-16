# Scrape traveler rating and traveler types of each hotel in the city and state you specified.
# For example, run 'python scraper_rating.py -city boston -state massachusetts -v'
# Data is stored in traveler_ratings.dat.

#!/usr/bin/python
# -*- coding: utf-8 -*-

from BeautifulSoup import BeautifulSoup
import sys
import time
import os
import logging
import argparse
import requests
from selenium import webdriver
import json

base_url = "https://www.tripadvisor.com"
user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.76 Safari/537.36"
headers = { 'User-Agent' : user_agent }
driver = webdriver.Chrome('./chromedriver')

parser = argparse.ArgumentParser(description = 'Scrape tripadvisor')
parser.add_argument('-datadir', type = str, help = 'Direcotry to store row html files', default = "data/")
parser.add_argument('-state', type = str, help = 'State for which the city data is required.', required = True)
parser.add_argument('-city', type = str, help = 'City for which the city data is required.', required = True)
parser.add_argument('-v', '--verbose', help = "Set log level to debug", action = "store_true")

args = parser.parse_args()


log = logging.getLogger(__name__)
log.setLevel(logging.ERROR)
if args.verbose:
    log.setLevel(logging.DEBUG)
loghandler = logging.StreamHandler(sys.stderr)
loghandler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
log.addHandler(loghandler)


def get_tourism_page(city, state):
    """
        Return the json containing the
        URL of the tourism city page
    """

    # EXAMPLE: http://www.tripadvisor.com/TypeAheadJson?query=boston%20massachusetts&action=API
    #          http://www.tripadvisor.com//TypeAheadJson?query=san%20francisco%20california&type=GEO&action=API
    url = "%s/TypeAheadJson?query=%s%%20%s&action=API" % (base_url, "%20".join(city.split()), state)
    log.info("URL TO REQUEST: %s \n" % url)

    # Given the url, request the HTML page
    headers = { 'User-Agent' : user_agent }
    response = requests.get(url, headers = headers)
    html = response.text.encode('utf-8')

    # Parse json to get url
    js = json.loads(html)
    results = js['results']
    log.info("RESULTS: %s \n " % results[0])
    urls = results[0]['urls'][0]
    log.info("URLS: %s \n " % urls)

    # get tourism page url
    tourism_url = urls['url']
    log.info("TOURISM PAGE URL: %s" % tourism_url)
    return tourism_url


def get_city_page(tourism_url):
    """
        Get the URL of the hotels of the city
        using the URL returned by the function
        get_tourism_page()
    """

    url = base_url + tourism_url

    # Given the url, request the HTML page
    headers = { 'User-Agent' : user_agent }
    response = requests.get(url, headers = headers)
    html = response.text.encode('utf-8')

    soup = BeautifulSoup(html)
    li = soup.find("li", {"class": "hotels twoLines"})
    city_url = li.find('a', href = True)
    log.info("CITY PAGE URL: %s" % city_url['href'])
    return city_url['href']


def get_hotellist_page(city_url, count):
    """
        Get the hotel list page given the url returned by
        get_city_page(). Return the html after saving
        it to the datadir
    """

    url = base_url + city_url
    # Sleep 2 sec before starting a new http request
    time.sleep(2)
    # Request page
    headers = { 'User-Agent' : user_agent }
    response = requests.get(url, headers = headers)
    html = response.text.encode('utf-8')
    return html


def parse_hotel_pages(html):
    '''
        Given a hotel list page, parse all the hotels on this page.
    '''

    soup = BeautifulSoup(html)
    # Get all the reviews on the page
    hotel_boxes = soup.findAll('div', {'class' : 'listing easyClear  p13n_imperfect '})

    # Details of each review on the page
    rating = []
    for hotel in hotel_boxes:
        name = hotel.find('div', {'class' : 'listing_title'}).find(text = True)
        hotel_url = base_url + hotel.find('div', {'class' : 'listing_title'}).find('a', href = True)['href']
        log.info('hotel_url: %s' % hotel_url)
        summary = get_hotel_rating(hotel_url)
        summary = [name + ':' + x for x in summary]
        rating += summary

    # Get next URL page if exists, else exit
    div = soup.find("div", {"class" : "unified pagination standard_pagination"})

    # if this is the last page, return
    if div.find('span', {'class' : 'nav next ui_button disabled'}):
        return rating, "no next page"

    # If it is not last page, get the next page
    hrefs = div.findAll('a', href = True)
    for href in hrefs:
        if href.find(text = True) == 'Next':
            next_page_url = base_url + href['href']
            log.info('next_page_url: ' + next_page_url)
            driver.get(next_page_url)
            time.sleep(1)
            html = driver.page_source.encode('utf-8')
            return rating, html


def get_hotel_rating(url):
    '''
        Given the hotel url, get the rating of this hotel.
    '''

    driver.get(url)
    time.sleep(1)
    hotel_html = driver.page_source.encode('utf-8')

    soup = BeautifulSoup(hotel_html)
    rating_box = soup.find('div', {'id' : 'filterControls'})
    summary = []

    traveler_ratings = rating_box.find('div', {'id' : 'ratingFilter'}).findAll('li')
    for item in traveler_ratings:
        rating = item.find('div', {'class' : 'row_label'}).find(text = True)
        spans = item.find('label').findAll('span')
        count = spans[2].text.replace(',', '')
        summary.append(rating.strip() + ':' + count)

    traveler_types = rating_box.find('div', {'class' : 'col segment '}).findAll('li')
    for item in traveler_types:
        label = item.find('label')
        type = label.find(text = True)
        count = label.find('span').text[1:-1].replace(',', '')
        summary.append(type.strip() + ':' + count)

    return summary


if __name__ == "__main__":

    start_time = time.time()
    # Get current directory
    current_dir = os.getcwd()
    filename = 'traveler_ratings.dat'
    if os.path.exists(filename):
        os.remove(filename)

    # Obtain the url of the toursim page
    tourism_url = get_tourism_page(args.city, args.state)
    # Get URL to obtaint the list of hotels in a specific city
    city_url = get_city_page(tourism_url)

    # Get the hotel page (first page of reveiws)
    url = base_url + city_url
    driver.get(url)
    time.sleep(1)
    hotellist_html = driver.page_source

    # Write review details to a local file
    with open(filename, "a") as myfile:
        page_count = 1
        next_page = hotellist_html
        while next_page != "no next page":
            print('\n****** hotel list page ' + str(page_count) + ' ******')
            # Parse the page with a list of reviews
            rating, next_page = parse_hotel_pages(next_page)
            # Write review details of the page to a local file
            for item in rating:
                myfile.write(item)
                myfile.write('\n')
            page_count += 1

    driver.close()
    print 'time: ', time.time() - start_time, 's'

