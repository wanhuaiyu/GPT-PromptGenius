import copy
from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, flash
from flask_login import LoginManager
from app.utils import *

bp = Blueprint('views', __name__)


@bp.route('/')
@bp.route('/index')
def index():
    return render_template('index.html')


# 登录路由
from flask import render_template, request, redirect, url_for

login_manager = LoginManager()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    # 用户未登录，重定向到登录页面
    return render_template('login.html')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return render_template('index.html')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if not username or not password or not confirm_password:
            flash('Please fill in all fields.')
        elif password != confirm_password:
            flash('Passwords do not match.')
        elif User.query.filter_by(username=username).first() is not None:
            flash('Username already exists.')
        else:
            user = User(username=username, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash('Registration succeeded.')
            return redirect(url_for('auth.login'))
    return render_template('register.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return render_template('index.html')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user is not None and user.check_password(password):
            login_user(user)
            return render_template('index.html')
        flash('Invalid username or password')
    return render_template('login.html')


# 登出路由
@bp.route('/logout')
@bp.route('/tools')
def tools():
    return render_template('tools.html')


@bp.route('/fetch_lan')
def fetch_lan():
    languages = [{"code": item.code, "name": item.name} for item in Languages.query.all()]
    return jsonify(languages)


@bp.route('/fetch_index_contents/<lan_code>/<location>')
def fetch_index_contents(lan_code, location):
    contents = {item.ID: item.content for item in IndexContents.query.filter(and_(IndexContents.lanCode == lan_code,
                                                                                  IndexContents.location == location)).all()}
    return jsonify(contents)


@bp.route('/fetch_banners/<lan_code>')
def fetch_banners(lan_code):
    banners = [{'image': item.image, 'url': item.url}
               for item in Banners.query.filter(Banners.lanCode == lan_code).all()]
    return jsonify(banners)


@bp.route('/fetch_tools/<lan_code>')
def fetch_tools(lan_code):
    tools = [{'name': item.name, 'desc': item.desc, 'url': item.url,
              'icon_src': item.icon_src, 'tags': item.tags.split(',')}
             for item in Tools.query.filter(Tools.lanCode == lan_code).all()]
    return jsonify(tools)


@bp.route('/submit_function', methods=['GET', 'POST'])
def submit_function():
    if request.method == 'POST':
        try:
            func_desc = request.json['func_desc']
            prompt_content = request.json['prompt_content']
            user_name = request.json['user_name']
            cur_time = datetime.now().strftime('%Y_%m_%d_%H_%M_%S')

            new_function = SubmitFunction(funcDesc=func_desc, createTime=cur_time,
                                          promptContent=prompt_content, userName=user_name)
            db.session.add(new_function)
            db.session.commit()

            return jsonify({'message': 'success'})
        except Exception as e:
            print(e)
            return jsonify({'message': 'error', 'error': str(e)})


@bp.route('/fetch_classes/<lan_code>')
def fetch_classes(lan_code):
    class_names = {item.ID: item.name
                   for item in ClassNames.query.filter(ClassNames.lanCode == lan_code).all()}
    classes = [{'ID': item.ID, 'name': class_names[item.ID],
                'childrens': [{'ID': child, 'name': class_names[child]} for child in item.childrens.split(',')]
                if item.childrens is not None else [],
                'icon': item.icon, 'icon_style': item.icon_style}
               for item in Classes.query.all()]
    return jsonify(classes)


@bp.route('/increase_count', methods=['GET', 'POST'])
def increase_count():
    if request.method == 'POST':
        try:
            functionprompt = FunctionPrompts.query.filter_by(
                lanCode=request.json['lan_code'],
                functionID=request.json['function_id'],
                semanticID=request.json['semantic_id']).first()
            if functionprompt:
                functionprompt.copied_count += 1
                db.session.commit()
            return jsonify({'message': 'success'})
        except Exception as e:
            print(e)
            return jsonify({'message': 'error', 'error': str(e)})


@bp.route('/fetch_prompt/<class_id>/<lan_code>')
def fetch_prompt(class_id, lan_code):
    result = []
    function_ids = [item.functionID
                    for item in FunctionPrompts.query.with_entities(FunctionPrompts.functionID).all()]

    # find all funcions that has the class
    if class_id == 'all_class' or class_id == 'popular':
        function_ids = [item.functionID
                        for item in FunctionPrompts.query.with_entities(FunctionPrompts.functionID).all()]
    else:
        function_ids = [item.ID
                        for item in Functions.query.with_entities(Functions.ID).
                            filter(Functions.classes.contains(class_id)).all()]

    # find all prompts that has the function
    for prompt in FunctionPrompts.query. \
            filter(and_(FunctionPrompts.functionID.in_(function_ids),
                        FunctionPrompts.lanCode == lan_code)).all():
        # prompt filter condition
        if class_id == 'popular' and int(prompt.priority) != 2:
            continue

        entry = {'content': prompt.content, 'lan_code': lan_code, 'semanticID': prompt.semanticID,
                 'functionID': prompt.functionID,
                 'author': prompt.author, 'author_link': prompt.author_link,
                 'model': prompt.model, 'function_id': prompt.functionID, 'copied_count': prompt.copied_count}
        tmp = get_prompt_info_for_render(entry)

        result.append(tmp)
    return jsonify({"content": result, "message": "success"})


@bp.route('/search_prompt/<search_text>/<lan_code>')
def search_prompt(search_text, lan_code):
    result = []

    for prompt in FunctionPrompts.query. \
            filter(and_(FunctionPrompts.lanCode == lan_code,
                        FunctionPrompts.content.contains(search_text))).all():
        entry = {'content': prompt.content, 'lan_code': lan_code, 'semanticID': prompt.semanticID,
                 'functionID': prompt.functionID,
                 'author': prompt.author, 'author_link': prompt.author_link,
                 'model': prompt.model, 'function_id': prompt.functionID, 'copied_count': prompt.copied_count}
        tmp = get_prompt_info_for_render(entry)
        result.append(tmp)

    return jsonify({"content": result, "message": "success"})
