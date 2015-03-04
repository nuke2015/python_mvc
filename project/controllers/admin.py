
import cgi
import os
from flask import Flask, render_template, abort, url_for, request, flash, session, redirect
from flaskext.markdown import Markdown
from project.models.mdx_github_gists import GitHubGistExtension
from project.models.mdx_strike import StrikeExtension
from project.models.mdx_quote import QuoteExtension
from project.models.mdx_code_multiline import MultilineCodeExtension
from werkzeug.contrib.atom import AtomFeed
import project.models.post as post
import project.models.user as user
import project.models.pagination as pagination
import project.models.settings as settings
from project.models.helper_functions import *
from project import app

# app = Flask('FlaskBlog')
md = Markdown(app)
md.register_extension(GitHubGistExtension)
md.register_extension(StrikeExtension)
md.register_extension(QuoteExtension)
md.register_extension(MultilineCodeExtension)
app.config.from_object('config')


@app.route('/newpost', methods=['GET', 'POST'])
@login_required()
def new_post():
    error = False
    error_type = 'validate'
    if request.method == 'POST':
        post_title = request.form.get('post-title').strip()
        post_full = request.form.get('post-full')

        if not post_title or not post_full:
            error = True
        else:
            tags = cgi.escape(request.form.get('post-tags'))
            tags_array = extract_tags(tags)
            post_data = {'title': post_title,
                         'preview': request.form.get('post-short'),
                         'body': post_full,
                         'tags': tags_array,
                         'author': session['user']['username']}

            post = postClass.validate_post_data(post_data)
            if request.form.get('post-preview') == '1':
                session['post-preview'] = post
                session[
                    'post-preview']['action'] = 'edit' if request.form.get('post-id') else 'add'
                if request.form.get('post-id'):
                    session[
                        'post-preview']['redirect'] = url_for('post_edit', id=request.form.get('post-id'))
                else:
                    session['post-preview']['redirect'] = url_for('new_post')
                return redirect(url_for('post_preview'))
            else:
                session.pop('post-preview', None)

                if request.form.get('post-id'):
                    response = postClass.edit_post(
                        request.form['post-id'], post)
                    if not response['error']:
                        flash('Post updated!', 'success')
                    else:
                        flash(response['error'], 'error')
                    return redirect(url_for('posts'))
                else:
                    response = postClass.create_new_post(post)
                    if response['error']:
                        error = True
                        error_type = 'post'
                        flash(response['error'], 'error')
                    else:
                        flash('New post created!', 'success')
    else:
        if session.get('post-preview') and session['post-preview']['action'] == 'edit':
            session.pop('post-preview', None)
    return render_template('new_post.html',
                           meta_title='New post',
                           error=error,
                           error_type=error_type)


@app.route('/post_preview')
@login_required()
def post_preview():
    post = session.get('post-preview')
    return render_template('preview.html', post=post, meta_title='Preview post::' + post['title'])


@app.route('/posts_list', defaults={'page': 1})
@app.route('/posts_list/page-<int:page>')
@login_required()
def posts(page):
    session.pop('post-preview', None)
    skip = (page - 1) * int(app.config['PER_PAGE'])
    posts = postClass.get_posts(int(app.config['PER_PAGE']), skip)
    count = postClass.get_total_count()
    pag = pagination.Pagination(page, app.config['PER_PAGE'], count)

    if not posts['data']:
        abort(404)

    return render_template('posts.html', posts=posts['data'], pagination=pag, meta_title='Posts')


@app.route('/post_edit?id=<id>')
@login_required()
def post_edit(id):
    post = postClass.get_post_by_id(id)
    if post['error']:
        flash(post['error'], 'error')
        return redirect(url_for('posts'))

    if session.get('post-preview') and session['post-preview']['action'] == 'add':
        session.pop('post-preview', None)
    return render_template('edit_post.html',
                           meta_title='Edit post::' + post['data']['title'],
                           post=post['data'],
                           error=False,
                           error_type=False)


@app.route('/post_delete?id=<id>')
@login_required()
def post_del(id):
    if postClass.get_total_count() > 1:
        response = postClass.delete_post(id)
        if response['data'] is True:
            flash('Post removed!', 'success')
        else:
            flash(response['error'], 'error')
    else:
        flash('Need to be at least one post..', 'error')

    return redirect(url_for('posts'))


@app.route('/users')
@login_required()
def users_list():
    users = userClass.get_users()
    return render_template('users.html', users=users['data'], meta_title='Users')


@app.route('/add_user')
@login_required()
def add_user():
    gravatar_url = userClass.get_gravatar_link()
    return render_template('add_user.html', gravatar_url=gravatar_url, meta_title='Add user')


@app.route('/edit_user?id=<id>')
@login_required()
def edit_user(id):
    user = userClass.get_user(id)
    return render_template('edit_user.html', user=user['data'], meta_title='Edit user')


@app.route('/delete_user?id=<id>')
@login_required()
def delete_user(id):
    if id != session['user']['username']:
        user = userClass.delete_user(id)
        if user['error']:
            flash(user['error'], 'error')
        else:
            flash('User deleted!', 'success')
    return redirect(url_for('users_list'))


@app.route('/save_user', methods=['POST'])
@login_required()
def save_user():
    post_data = {
        '_id': request.form.get('user-id', None).lower().strip(),
        'email': request.form.get('user-email', None),
        'old_pass': request.form.get('user-old-password', None),
        'new_pass': request.form.get('user-new-password', None),
        'new_pass_again': request.form.get('user-new-password-again', None),
        'update': request.form.get('user-update', False)
    }
    if not post_data['email'] or not post_data['_id']:
        flash('Username and Email are required..', 'error')
        if post_data['update']:
                return redirect(url_for('edit_user', id=post_data['_id']))
        else:
            return redirect(url_for('add_user'))
    else:
        user = userClass.save_user(post_data)
        if user['error']:
            flash(user['error'], 'error')
            if post_data['update']:
                return redirect(url_for('edit_user', id=post_data['_id']))
            else:
                return redirect(url_for('add_user'))
        else:
            message = 'User updated!' if post_data['update'] else 'User added!'
            flash(message, 'success')
    return redirect(url_for('edit_user', id=post_data['_id']))


@app.route('/settings', methods=['GET', 'POST'])
@login_required()
def blog_settings():
    error = None
    error_type = 'validate'
    if request.method == 'POST':
        blog_data = {
            'title': request.form.get('blog-title', None),
            'description': request.form.get('blog-description', None),
            'per_page': request.form.get('blog-perpage', None),
            'text_search': request.form.get('blog-text-search', None)
        }
        blog_data['text_search'] = 1 if blog_data['text_search'] else 0
        for key, value in blog_data.items():
            if not value and key != 'text_search' and key != 'description':
                error = True
                break
        if not error:
            update_result = settingsClass.update_settings(blog_data)
            if update_result['error']:
                flash(update_result['error'], 'error')
            else:
                flash('Settings updated!', 'success')
                return redirect(url_for('blog_settings'))

    return render_template('settings.html',
                           default_settings=app.config,
                           meta_title='Settings',
                           error=error,
                           error_type=error_type)


settingsClass = settings.Settings(app.config)
postClass = post.Post(app.config)
userClass = user.User(app.config)
