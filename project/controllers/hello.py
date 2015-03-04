# -*- coding: utf-8 -*-
from project import app
from flask import render_template, request
from flask.ext.wtf import Form, TextField, validators


class CreateForm(Form):
    text = TextField(u'Text:', [validators.Length(min=1, max=20)])


@app.route('/hello/test')
def test():
    return 'welcome to python!'
