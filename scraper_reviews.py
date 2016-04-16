# Given a hotel URL in the main function, scrape all the review details.
# Data is stored in reviews.dat.


#!/usr/bin/python
# -*- coding: utf-8 -*-

from BeautifulSoup import BeautifulSoup
import sys
import time
import os
import logging
import requests
from selenium import webdriver

base_url = "https://www.tripadvisor.com"
user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.76 Safari/537.36"
headers = { 'User-Agent' : user_agent }
driver = webdriver.Chrome('./chromedriver')


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
loghandler = logging.StreamHandler(sys.stderr)
loghandler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
log.addHandler(loghandler)

def parse_hotellist_page(html):
    """ Parse the html pages returned by get_hotellist_page().
        Return the next url page to scrape (a city can have
        more than one page of hotels) if there is, else exit
        the script.
    """

    soup = BeautifulSoup(html)
    # Extract hotel name, star rating and number of reviews
    hotel_boxes = soup.findAll('div', {'class' : 'listing easyClear  p13n_imperfect '})
    for hotel_box in hotel_boxes:
        name = hotel_box.find('div', {'class' : 'listing_title'}).find(text = True)
        try:
            rating = hotel_box.find('div', {'class' : 'listing_rating'})
            reviews = rating.find('span', {'class' : 'more'}).find(text = True)
            stars = hotel_box.find("img", {"class" : "sprite-ratings"})
        except Exception, e:
            log.error("No ratings for this hotel")
            reviews = "N/A"
            stars = 'N/A'

        if stars != 'N/A':
            #log.info("Stars: %s" % stars['alt'].split()[0])
            stars = stars['alt'].split()[0]
        log.info("HOTEL NAME: %s" % name)
        log.info("HOTEL REVIEWS: %s" % reviews)
        log.info("HOTEL STAR RATING: %s \n" % stars)

    # Get next URL page if exists, else exit
    div = soup.find("div", {"class" : "unified pagination standard_pagination"})
    # check if last page
    if div.find('span', {'class' : 'nav next ui_button disabled'}):
        log.info("We reached last page")
        sys.exit()
    # If it is not las page there must be the Next URL
    hrefs = div.findAll('a', href = True)
    for href in hrefs:
        if href.find(text = True) == 'Next':
            log.info("Next url is %s" % href['href'])
            return href['href']


def get_hotel_page(html):
    """ Given the hotel listing page, return the page of the first hotel in the listing.
    """

    soup = BeautifulSoup(html)
    hotel = soup.find('div', {'class' : 'listing easyClear  p13n_imperfect '})
    title = hotel.find('div', {'class' : 'listing_title'})
    hotel_url = title.find('a', href = True)['href']
    log.info("hotel_url: %s \n" % hotel_url)

    url = base_url + hotel_url
    time.sleep(2)
    # Request page
    headers = { 'User-Agent' : user_agent }
    response = requests.get(url, headers = headers)
    html = response.text.encode('utf-8')
    return html


def parse_review_pages(html):
    """ Given a hotel page, parse all the reviews in this page.
        Return result of parsing and the next page of reviews.
    """

    soup = BeautifulSoup(html)
    # Get all the reviews on the page
    reviews = soup.find('div', {'id' : 'REVIEWS'}).findAll('div', {'class' : 'innerBubble'})

    urls = set()
    # Details of each review on the page
    hotel_reviews = []
    for review in reviews:
        # Get the url of a review
        review_url = base_url + review.find('a', href = True)['href']
        # Avoid duplicate reviews
        if review_url not in urls:
            urls.add(review_url)
            log.info("user_review_url: %s" % review_url)
            # Get the html of a review
            driver.get(review_url)
            time.sleep(1)
            review_html = driver.page_source.encode('utf-8')
            # Get the detail of a review
            review_detail = get_review_detail(review_html)
            # Aggregate the details of reviews on a page
            review_id = 'review_' + review_url.split('-')[3][1:] + ':'
            review_detail = [review_id + x for x in review_detail]
            hotel_reviews += review_detail

    # Get next URL page if exists, else exit
    div = soup.find("div", {"class" : "unified pagination "})

    # if this is the last page, return
    if div.find('span', {'class' : 'nav next disabled'}):
        return hotel_reviews, "no next page"

    # If it is not last page, get the next page
    hrefs = div.findAll('a', href = True)
    for href in hrefs:
        if href.find(text = True) == 'Next':
            next_page_url = base_url + href['href']
            log.info('next_page_url: ' + next_page_url)
            driver.get(next_page_url)
            time.sleep(1)
            html = driver.page_source.encode('utf-8')
            return hotel_reviews, html


def get_review_detail(html):
    """ Given a review page, return the details of the review.
    """

    soup = BeautifulSoup(html)

    review_detail = []
    rating_list = soup.find('div', {'class' : "rating-list"})
    if rating_list:
        ratings = rating_list.findAll('li', {'class' : 'recommend-answer'})
        for rating in ratings:
            star = rating.find('img')['alt'].split()[0]
            description = rating.find('div', {'class' : 'recommend-description'}).find(text = True)
            review_detail.append(description + ':' + star)

    return review_detail


if __name__ == "__main__":

    start_time = time.time()
    # Get current directory
    current_dir = os.getcwd()
    filename = 'reviews.dat'
    if os.path.exists(filename):
        os.remove(filename)

    # Scrape reviews of hotel 'Omni Parker House'
    url = 'https://www.tripadvisor.com/Hotel_Review-g60745-d89599-Reviews-Omni_Parker_House-Boston_Massachusetts.html'
    driver.get(url)
    time.sleep(1)
    hotel_html = driver.page_source

    # Write review details to a local file
    with open(filename, "a") as myfile:
        page_count = 1
        next_page = hotel_html
        while next_page != "no next page":
            print('\n****** page ' + str(page_count) + ' ******')
            # Parse the page with a list of reviews
            detail, next_page = parse_review_pages(next_page)
            # Write review details of the page to a local file
            for item in detail:
                myfile.write(item)
                myfile.write('\n')
            page_count += 1

    driver.close()
    print 'time: ', time.time() - start_time, 's'
