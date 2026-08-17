"""Deliberately flawed code used to demonstrate the reviewer on a real PR.

Not imported by anything. Each function contains a defect from one of the
categories the bot is prompted to report.
"""

import sqlite3


def average(values):
    # ZeroDivisionError when values is empty
    return sum(values) / len(values)


def get_user(conn, username):
    # SQL injection: username is interpolated straight into the statement
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE name = '" + username + "'")
    return cursor.fetchone()


def read_config(path):
    # File handle is never closed
    f = open(path, "r", encoding="utf-8")
    return f.read()


def last_item(items):
    # IndexError on an empty list; the name implies it is always safe
    return items[len(items) - 1]
