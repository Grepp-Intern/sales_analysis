#-*- coding: utf-8 -*-

from selenium import webdriver
import requests
from bs4 import BeautifulSoup
import time
import re
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

def write_file(urls):
	f = open("urls.txt", 'w')
	f.write('\n'.join(urls))
	f.close()

def get_html(url):
	_html_ = ""
	resp = requests.get(url)
	if resp.status_code == 200:
		_html = resp.text
	return _html

def parse_html(html):
	course = list()
	soup = BeautifulSoup(html, 'html.parser')
	title = soup.find("div", {"id": "item-header-content"}).find("h1").text.strip()
	students = int(soup.find("div", {"class": "students"}).text.replace(u'명','').strip())
	price_area = soup.find("li", {"class": "course_price"})
	discount = price_area.find("del")

	if discount is None:
		price = price_area.find("span", {"class": "woocommerce-Price-amount"})
		
		if price is None:
			price = 0
		else:
			price = int(price.text.replace(',','').replace(u'₩','').strip())
		
	else:
		price = price_area.find_all("span", {"class": "woocommerce-Price-amount"})[1]
		price = int(price.text.replace(',','').replace(u'₩','').strip())

	course = [title, students, price]
	return course

def remove_html_tags(data):
    p = re.compile(r'<.*?>')
    return p.sub('', data)

def get_urls_by_driver(driver):
	urls = []
	html = driver.page_source
	soup = BeautifulSoup(html,'html.parser')

	cource_dir_list = soup.find('div', id="course-dir-list")
	cource_list = cource_dir_list.find('ul', id="course-list")
	cource_list_items = cource_list.find_all('div', {'class':"item-title"})

	for item in cource_list_items:
		url_tag = item.find("a")
		_url = url_tag["href"]
		urls.append(_url)
	return urls

def get_current_page_number(driver):
	html = driver.page_source
	soup = BeautifulSoup(html,'html.parser')

	cource_dir_list = soup.find('div', id="course-dir-list")
	page_top = cource_dir_list.find('div', id="pag-top")
	pagination_links = page_top.find('div', {'class':"pagination-links"})
	currnet_page_number_html = pagination_links.find('span', {'class':"page-numbers current"})
	currnet_page_number = int(remove_html_tags(str(currnet_page_number_html)))
	return currnet_page_number

def get_last_page_number(driver):
	html = driver.page_source
	soup = BeautifulSoup(html,'html.parser')

	cource_dir_list = soup.find('div', id="course-dir-list")
	page_top = cource_dir_list.find('div', id="pag-top")
	pagination_links = page_top.find('div', {'class':"pagination-links"})
	page_numbers = pagination_links.find_all('a', {'class':"page-numbers"})
	last_page_number = int(remove_html_tags(str(page_numbers[-2])))
	return last_page_number

#Chrome('./chromedriver')
#PhantomJS()
def get_all_urls_use_selenium():
	
	driver = webdriver.PhantomJS()
	driver.get('https://www.inflearn.com/all-courses/')
	next_page_number_xpath = "//div[@id='course-dir-list']/div[@id='pag-top']/div[@class='pagination-links']/a[@class='next page-numbers']"
	current_xpath_element = ''
	prev_xpath_element = ''
	currnet_page_number = get_current_page_number(driver)
	last_page_number = get_last_page_number(driver)
	all_urls = []
	page = 1

	while True:
		print page
		page += 1
		try:
			current_xpath_element = WebDriverWait(driver, 10) \
			.until(EC.presence_of_element_located((By.XPATH, next_page_number_xpath)))
		except Exception as e:
			print e
			print 'try again'

		while True:
			if current_xpath_element != prev_xpath_element or currnet_page_number == last_page_number:
				prev_xpath_element = current_xpath_element
				urls_one_page = get_urls_by_driver(driver)
				for url in urls_one_page:
					if url not in all_urls:
						all_urls.append(url)
				break;
			else:
				time.sleep(1)
				if currnet_page_number == get_current_page_number(driver):
					continue
				else :
					currnet_page_number = get_current_page_number(driver)
				if currnet_page_number != last_page_number:
					current_xpath_element = driver.find_element_by_xpath(next_page_number_xpath)
		if currnet_page_number == last_page_number:
			break;
		current_xpath_element.click()

	driver.quit()
	print "url update finish"
	return all_urls
