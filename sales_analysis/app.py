#-*- coding: utf-8 -*-

from __future__ import with_statement
from contextlib import closing
from flask import Flask, request, session, g, redirect, url_for, abort, render_template, flash
import sqlite3
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pytz import timezone
import time
import crawling
import logging
from apscheduler.schedulers.background import BackgroundScheduler

DATABASE = './crawling.db'
DEBUG = True
SECRET_KEY = 'development key'
USERNAME = 'admin'
PASSWORD = 'default'

app = Flask(__name__)
app.config.from_object(__name__)

def connect_db():
	return sqlite3.connect(app.config['DATABASE'])

def init_db():
	with closing(connect_db()) as db:
		with app.open_resource('schema.sql') as f:
			db.cursor().executescript(f.read())
		db.commit()

@app.before_request
def before_request():
	g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
	g.db.close()

@app.route('/index')
def index():
	sql = "SELECT A.UPDATE_DATE, SUM(A.STUDENT_COUNT * A.PRICE) AS TOTAL_REVENUE, SUM((A.STUDENT_COUNT - B.STUDENT_COUNT) * A.PRICE) AS DAILY_REVENUE, SUM((A.STUDENT_COUNT - B.STUDENT_COUNT) * A.PRICE) * 0.3 AS COMPANY_REVENUE FROM SALES A, SALES B WHERE A.ID = B.ID AND A.UPDATE_DATE = DATE(B.UPDATE_DATE, '+1 day') GROUP BY A.UPDATE_DATE ORDER BY A.UPDATE_DATE"
	cur = g.db.execute(sql)
	index_table = [dict(DATE=row[0], TOTAL_REVENUE=format(int(row[1]), ','), DAILY_REVENUE=format(int(row[2]), ','), COMPANY_REVENUE=format(int(row[3]), ',')) for row in cur.fetchall()]

	revenue_predict = 0
	for index in index_table:
		revenue_predict = revenue_predict + int(index['COMPANY_REVENUE'].replace(',',''))
	revenue_predict = int( (revenue_predict/len(index_table) * 9 * 365) / (10 * 12) )

	monthly_revenue_predict = format(revenue_predict, ',')

	return render_template('index.html', INDEX_TABLE=index_table, MONTHLY_REVENUE_PREDICT=monthly_revenue_predict)

@app.route('/daily/<date>')
def daily_index(date):
	sql = "SELECT COURSES.ID, COURSES.TITLE, A.PRICE, A.STUDENT_COUNT, SUM((A.STUDENT_COUNT - B.STUDENT_COUNT) * A.PRICE) AS REVENUE, A.UPDATE_DATE FROM COURSES, SALES A, SALES B WHERE COURSES.ID = A.ID AND A.ID = B.ID AND A.UPDATE_DATE = DATE(B.UPDATE_DATE, '+1 day') AND A.UPDATE_DATE = (?) GROUP BY A.ID, A.UPDATE_DATE ORDER BY REVENUE DESC"
	cur = g.db.execute(sql, [date])
	courses = [dict(ID=row[0], TITLE=row[1], PRICE=format(int(row[2]), ','), STUDENT_COUNT=format(int(row[3]), ','), REVENUE=format(int(row[4]), ','), UPDATE_DATE=row[5]) for row in cur.fetchall()]

	return render_template('daily.html', DATE=date, COURSES=courses)

@app.route('/')
def hello():
	return "enter the indexing page"

@app.route('/course/<course_id>')
def course_index(course_id):
	sql = "SELECT TITLE FROM COURSES WHERE ID = (?)"
	cur = g.db.execute(sql, [course_id])
	title = cur.fetchall()[0][0]

	sql = "SELECT STUDENT_COUNT, UPDATE_DATE FROM SALES WHERE ID = (?) LIMIT 7"
	cur = g.db.execute(sql, [course_id])
	student_count = [dict(STUDENT_COUNT=format(int(row[0]), ','), UPDATE_DATE=row[1]) for row in cur.fetchall()]

	sql = "SELECT A.UPDATE_DATE, A.PRICE FROM SALES A, SALES B WHERE A.ID = (?) AND A.ID = B.ID AND A.PRICE <> B.PRICE"
	cur = g.db.execute(sql, [course_id])
	prices = [dict(UPDATE_DATE=row[0], PRICE=format(int(row[1]), ',')) for row in cur.fetchall()]

	return render_template('course.html', ID=course_id, TITLE=title, STUDENT_COUNT=student_count, PRICE=prices)

@app.route('/update')
def update():
	crawling.write_file(crawling.get_all_urls_use_selenium())
	file = open('./urls.txt')
	URL_list = file.readlines()
	file.close()

	for i in range(len(URL_list)):
		URL = URL_list[i]

		course = list()
		course.append(URL)
		html = crawling.get_html(URL)
		course = course + crawling.parse_html(html)
		course.append(datetime.now().strftime('%Y-%m-%d'))

		sql = "INSERT OR IGNORE INTO COURSES (URL, TITLE, RELEASE_DATE) VALUES(?, ?, ?)"
		data = (course[0], course[1], course[4])
		with app.app_context():
			g.db = connect_db()
			g.db.execute(sql, data)
			g.db.commit()

		sql = "SELECT ID FROM COURSES WHERE URL = (?)"
		with app.app_context():
			g.db = connect_db()	
			cur = g.db.execute(sql, [URL])
		course_id = cur.fetchall()

		sql = "INSERT OR IGNORE INTO SALES (ID, UPDATE_DATE, PRICE, STUDENT_COUNT) VALUES(?, ?, ?, ?)"
		data = (int(course_id[0][0]), course[4], course[3], course[2])
		with app.app_context():
			g.db = connect_db()
			g.db.execute(sql, data)
			g.db.commit()

		time.sleep(1)
	
	return redirect(url_for('index'))

@app.route('/delete')
def delete():
	sql = "DELETE FROM COURSES"
	g.db.execute(sql)
	g.db.commit()

	sql = "DELETE FROM SALES"
	g.db.execute(sql)
	g.db.commit()
	return redirect(url_for('show_courses'))

@app.route('/ex_html')
def ex_html():
	return render_template('ex_html.html');

if __name__ == '__main__':
	log = logging.getLogger('apscheduler.executors.default')
	log.setLevel(logging.INFO)  # DEBUG

	fmt = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
	h = logging.StreamHandler()
	h.setFormatter(fmt)
	log.addHandler(h)

	sched = BackgroundScheduler(timezone='utc')
	sched.add_job(update, 'cron', hour='0-23', minute='30')
	sched.start()
	
	app.run(host='0.0.0.0', debug=True, port=1024)
