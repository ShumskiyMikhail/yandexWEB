from flask import Flask, render_template, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, date, timedelta
from functools import wraps
import os
import secrets
from sqlalchemy import func, case, extract
import logging
from logging.handlers import RotatingFileHandler
from markupsafe import escape

from flask import request, jsonify

from models import db, login_manager, User, Meal, Order, Allergy, Feedback, Inventory, \
    PurchaseRequest, Notification, PreparedMeal, Subscription, MealIngredient
from forms import LoginForm, RegistrationForm, AllergyForm, OrderForm, FeedbackForm, PurchaseRequestForm, InventoryForm, \
    PrepareMealForm, SubscriptionForm

from flask_wtf.csrf import CSRFProtect
from flask import Blueprint

app = Flask(__name__)
app.config['SECRET_KEY'] = 'school-food-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school_food.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

csrf = CSRFProtect(app)

if not app.debug:
    file_handler = RotatingFileHandler('school_food.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему.'


def role_required(roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Войдите в систему.', 'danger')
                return redirect(url_for('login'))
            if current_user.role not in roles:
                app.logger.warning(f'Unauthorized access attempt by user {current_user.id} to {request.endpoint}')
                flash('У вас нет прав для доступа к этой странице.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def create_tables():
    with app.app_context():
        db.create_all()

        admin_exists = User.query.filter_by(username='admin').first()
        if not admin_exists:
            print("=" * 60)
            print("НАЧАЛЬНАЯ НАСТРОЙКА БАЗЫ ДАННЫХ")
            print("=" * 60)

            admin = User(
                username='admin',
                email='admin@school.ru',
                role='администратор',
                grade='Админ',
                balance=10000.00
            )
            admin.set_password('Admin123!')

            chef = User(
                username='chef',
                email='chef@school.ru',
                role='повар',
                grade='Повар',
                balance=5000.00
            )
            chef.set_password('Chef123!')

            student = User(
                username='student',
                email='student@school.ru',
                role='ученик',
                grade='10А',
                balance=0.00
            )
            student.set_password('Student123!')

            db.session.add_all([admin, chef, student])
            db.session.commit()
            print("✅ Созданы тестовые пользователи")

            if Inventory.query.count() == 0:
                ingredients = [
                    Inventory(ingredient='Мука пшеничная', quantity=50.0, unit='кг', min_quantity=10.0),
                    Inventory(ingredient='Сахар', quantity=30.0, unit='кг', min_quantity=5.0),
                    Inventory(ingredient='Яйца', quantity=200.0, unit='шт', min_quantity=50.0),
                    Inventory(ingredient='Молоко', quantity=40.0, unit='л', min_quantity=10.0),
                    Inventory(ingredient='Масло сливочное', quantity=10.0, unit='кг', min_quantity=2.0),
                    Inventory(ingredient='Картофель', quantity=100.0, unit='кг', min_quantity=20.0),
                    Inventory(ingredient='Морковь', quantity=30.0, unit='кг', min_quantity=5.0),
                    Inventory(ingredient='Лук', quantity=20.0, unit='кг', min_quantity=5.0),
                    Inventory(ingredient='Курица', quantity=25.0, unit='кг', min_quantity=10.0),
                    Inventory(ingredient='Говядина', quantity=15.0, unit='кг', min_quantity=5.0),
                    Inventory(ingredient='Рис', quantity=20.0, unit='кг', min_quantity=5.0),
                    Inventory(ingredient='Макароны', quantity=25.0, unit='кг', min_quantity=5.0),
                    Inventory(ingredient='Помидоры', quantity=15.0, unit='кг', min_quantity=3.0),
                    Inventory(ingredient='Огурцы', quantity=10.0, unit='кг', min_quantity=2.0),
                    Inventory(ingredient='Капуста', quantity=20.0, unit='кг', min_quantity=5.0),
                    Inventory(ingredient='Сметана', quantity=15.0, unit='кг', min_quantity=3.0),
                    Inventory(ingredient='Сыр', quantity=10.0, unit='кг', min_quantity=2.0),
                    Inventory(ingredient='Хлеб', quantity=50.0, unit='шт', min_quantity=10.0),
                    Inventory(ingredient='Масло растительное', quantity=20.0, unit='л', min_quantity=5.0),
                    Inventory(ingredient='Соль', quantity=10.0, unit='кг', min_quantity=2.0),
                    Inventory(ingredient='Колбаса', quantity=10.0, unit='кг', min_quantity=2.0),
                    Inventory(ingredient='Сухофрукты', quantity=5.0, unit='кг', min_quantity=1.0),
                    Inventory(ingredient='Чай', quantity=1.0, unit='кг', min_quantity=0.2),
                ]
                db.session.add_all(ingredients)
                db.session.commit()
                print(f"✅ Создано {len(ingredients)} ингредиентов")

            if Meal.query.count() == 0:
                meals = [
                    Meal(name='Каша манная', description='Манная каша на молоке с сахаром', meal_type='завтрак',
                         price=80.0, calories=250, ingredients='манка, молоко, сахар, масло',
                         allergens='глютен, молоко', is_available=True),
                    Meal(name='Омлет с сыром', description='Пышный омлет с сыром', meal_type='завтрак', price=95.0,
                         calories=300, ingredients='яйца, молоко, сыр, масло', allergens='яйца, молоко',
                         is_available=True),
                    Meal(name='Бутерброды с колбасой', description='Бутерброды с докторской колбасой',
                         meal_type='завтрак', price=75.0, calories=180, ingredients='хлеб, колбаса, масло',
                         allergens='глютен', is_available=True),
                    Meal(name='Суп куриный с лапшой', description='Наваристый куриный суп с лапшой', meal_type='обед',
                         price=120.0, calories=350, ingredients='курица, лапша, морковь, лук, картофель',
                         allergens='глютен', is_available=True),
                    Meal(name='Котлета с картофельным пюре', description='Куриная котлета с пюре и овощами',
                         meal_type='обед', price=135.0, calories=450,
                         ingredients='курица, картофель, молоко, масло, лук', allergens='', is_available=True),
                    Meal(name='Макароны по-флотски', description='Макароны с мясным фаршем', meal_type='обед',
                         price=110.0, calories=380, ingredients='макароны, говядина, лук, морковь', allergens='глютен',
                         is_available=True),
                    Meal(name='Компот из сухофруктов', description='Компот из кураги и изюма', meal_type='напиток',
                         price=25.0, calories=80, ingredients='сухофрукты, сахар, вода', allergens='',
                         is_available=True),
                    Meal(name='Чай с сахаром', description='Черный чай с сахаром', meal_type='напиток', price=20.0,
                         calories=50, ingredients='чай, сахар, вода', allergens='', is_available=True),
                ]
                db.session.add_all(meals)
                db.session.commit()
                print(f"✅ Создано {len(meals)} блюд")

            print("\n" + "=" * 60)
            print("✅ БАЗА ДАННЫХ ГОТОВА К РАБОТЕ!")
            print("=" * 60)
            print("\nДанные для входа:")
            print("  👨‍💼  Администратор: admin / Admin123!")
            print("  👨‍🍳  Повар:       chef / Chef123!")
            print("  👨‍🎓  Ученик:      student / Student123!")
            print("\n💡 Ученик начинается с балансом 0 руб.")
        else:
            print("=" * 60)
            print("✅ БАЗА ДАННЫХ УЖЕ НАСТРОЕНА")
            print("=" * 60)
            print(f"👥 Всего пользователей: {User.query.count()}")
            print(f"🍽️  Блюд в меню: {Meal.query.count()}")
            print(f"📦 Ингредиентов на складе: {Inventory.query.count()}")
            print(f"📊 Всего заказов: {Order.query.count()}")


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('home'))


@app.route('/home')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash(f'Добро пожаловать, {user.username}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль.', 'danger')

    return render_template('login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            grade=form.grade.data,
            role='ученик',
            balance=0.00
        )
        user.set_password(form.password.data)

        try:
            db.session.add(user)
            db.session.commit()
            flash('Регистрация успешна! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Ошибка при регистрации. Пользователь с таким именем или email уже существует.', 'danger')

    return render_template('register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'ученик':
        return redirect(url_for('student_dashboard'))
    elif current_user.role == 'повар':
        return redirect(url_for('chef_dashboard'))
    elif current_user.role == 'администратор':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))


@app.route('/notifications')
@login_required
def notifications():
    user_notifications = Notification.query.filter(
        Notification.user_id == current_user.id
    ).order_by(Notification.created_at.desc()).all()

    for notification in user_notifications:
        if not notification.is_read:
            notification.is_read = True

    db.session.commit()

    return render_template('notifications.html', notifications=user_notifications)


@app.route('/api/notifications/unread')
@login_required
def unread_notifications():
    count = Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()
    return jsonify({'count': count})


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(current_password):
            flash('Неверный текущий пароль.', 'danger')
            return redirect(url_for('change_password'))

        if new_password != confirm_password:
            flash('Новые пароли не совпадают.', 'danger')
            return redirect(url_for('change_password'))

        if len(new_password) < 6:
            flash('Пароль должен содержать минимум 6 символов.', 'danger')
            return redirect(url_for('change_password'))

        current_user.set_password(new_password)
        db.session.commit()

        flash('Пароль успешно изменен!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('change_password.html')


@app.route('/student')
@login_required
@role_required(['ученик'])
def student_dashboard():
    today = date.today()

    orders = Order.query.filter(
        Order.user_id == current_user.id,
        Order.meal_date >= today
    ).order_by(Order.meal_date.desc()).limit(5).all()

    active_subscription = Subscription.query.filter(
        Subscription.user_id == current_user.id,
        Subscription.is_active == True
    ).filter(
        Subscription.start_date <= today,
        Subscription.end_date >= today
    ).first()

    notifications_list = Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).order_by(Notification.created_at.desc()).limit(3).all()

    total_spent = db.session.query(func.sum(Order.total_price)).filter(
        Order.user_id == current_user.id,
        Order.status == 'paid'
    ).scalar() or 0.0

    return render_template('student_dashboard.html',
                           orders=orders,
                           total_spent=total_spent,
                           notifications=notifications_list,
                           active_subscription=active_subscription)


@app.route('/add_balance', methods=['GET', 'POST'])
@login_required
@role_required(['ученик'])
def add_balance():
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))

            if amount <= 0:
                flash('Сумма должна быть больше 0.', 'danger')
                return redirect(url_for('add_balance'))

            if amount > 10000:
                flash('Сумма не может превышать 10 000 руб.', 'danger')
                return redirect(url_for('add_balance'))

            current_user.balance += amount

            notification = Notification(
                user_id=current_user.id,
                title='Пополнение баланса',
                message=f'Ваш баланс пополнен на {amount} руб. Текущий баланс: {current_user.balance} руб.',
                type='оплата'
            )
            db.session.add(notification)

            db.session.commit()

            flash(f'Баланс успешно пополнен на {amount} руб.!', 'success')
            return redirect(url_for('student_dashboard'))

        except ValueError:
            flash('Некорректная сумма.', 'danger')
            return redirect(url_for('add_balance'))

    return render_template('add_balance.html')


@app.route('/allergies', methods=['GET', 'POST'])
@login_required
@role_required(['ученик'])
def allergies():
    form = AllergyForm()

    if form.validate_on_submit():
        allergy = Allergy(
            user_id=current_user.id,
            allergen=form.allergen.data,
            severity=form.severity.data,
            notes=form.notes.data
        )
        db.session.add(allergy)
        db.session.commit()
        flash('Аллергия добавлена!', 'success')
        return redirect(url_for('allergies'))

    user_allergies = Allergy.query.filter(Allergy.user_id == current_user.id).all()
    return render_template('allergies.html', form=form, allergies=user_allergies)


@app.route('/feedback', methods=['GET', 'POST'])
@login_required
@role_required(['ученик'])
def feedback():
    form = FeedbackForm()

    available_meals = Meal.query.filter(
        Meal.is_available == True
    ).order_by(Meal.name).all()

    if available_meals:
        form.meal_id.choices = [(m.id, f"{m.name} ({m.meal_type})") for m in available_meals]
    else:
        form.meal_id.choices = [(0, 'Нет доступных блюд')]

    if form.validate_on_submit():
        meal = Meal.query.get(form.meal_id.data)

        if not meal:
            flash('Блюдо не найдено.', 'danger')
            return redirect(url_for('feedback'))

        existing_feedback = Feedback.query.filter(
            Feedback.user_id == current_user.id,
            Feedback.meal_id == meal.id
        ).first()

        if existing_feedback:
            existing_feedback.rating = form.rating.data
            existing_feedback.comment = form.comment.data
            flash('Отзыв обновлен!', 'success')
        else:
            new_feedback = Feedback(
                user_id=current_user.id,
                meal_id=meal.id,
                rating=form.rating.data,
                comment=form.comment.data
            )
            db.session.add(new_feedback)
            flash('Спасибо за отзыв!', 'success')

        db.session.commit()
        return redirect(url_for('feedback'))

    user_feedbacks = db.session.query(
        Feedback,
        Meal.name.label('meal_name'),
        Meal.meal_type.label('meal_type'),
        User.username.label('username')
    ).join(
        Meal, Feedback.meal_id == Meal.id
    ).join(
        User, Feedback.user_id == User.id
    ).filter(
        Feedback.user_id == current_user.id
    ).order_by(
        Feedback.created_at.desc()
    ).all()

    feedbacks = []
    for fb, meal_name, meal_type, username in user_feedbacks:
        feedbacks.append({
            'id': fb.id,
            'rating': fb.rating,
            'comment': fb.comment,
            'created_at': fb.created_at,
            'meal_name': meal_name,
            'meal_type': meal_type,
            'username': username,
            'is_own': fb.user_id == current_user.id
        })

    return render_template('feedback.html',
                           form=form,
                           feedbacks=feedbacks,
                           available_meals=available_meals)


@app.route('/feedback/<int:feedback_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['ученик'])
def edit_feedback(feedback_id):
    feedback = Feedback.query.get_or_404(feedback_id)

    if feedback.user_id != current_user.id:
        flash('Это не ваш отзыв.', 'danger')
        return redirect(url_for('feedback'))

    form = FeedbackForm(obj=feedback)

    available_meals = Meal.query.filter(
        Meal.is_available == True
    ).order_by(Meal.name).all()

    form.meal_id.choices = [(m.id, f"{m.name} ({m.meal_type})") for m in available_meals]

    if form.rating.data is None:
        form.rating.data = feedback.rating

    if form.validate_on_submit():
        feedback.meal_id = form.meal_id.data
        feedback.rating = form.rating.data
        feedback.comment = form.comment.data

        db.session.commit()
        flash('Отзыв обновлен!', 'success')
        return redirect(url_for('feedback'))

    return render_template('edit_feedback.html', form=form, feedback=feedback)


@app.route('/feedback/<int:feedback_id>/delete', methods=['POST'])
@login_required
@role_required(['ученик'])
def delete_feedback(feedback_id):
    feedback = Feedback.query.get_or_404(feedback_id)

    if feedback.user_id != current_user.id:
        flash('Это не ваш отзыв.', 'danger')
        return redirect(url_for('feedback'))

    db.session.delete(feedback)
    db.session.commit()

    flash('Отзыв удален!', 'success')
    return redirect(url_for('feedback'))


@app.route('/menu')
@login_required
def menu():
    meal_type = request.args.get('type', 'завтрак')

    all_meals = Meal.query.filter(
        Meal.meal_type == meal_type,
        Meal.is_available == True
    ).all()

    available_meals = []
    for meal in all_meals:
        if meal.get_available_quantity() > 0:
            available_meals.append(meal)

    return render_template('menu.html',
                           meals=available_meals,
                           meal_type=meal_type,
                           total_meals=len(all_meals),
                           available_meals_count=len(available_meals))


@app.route('/order', methods=['GET', 'POST'])
@login_required
@role_required(['ученик'])
def order():
    form = OrderForm()

    meal_type = request.args.get('type', request.form.get('meal_type', 'завтрак'))
    form.meal_type.data = meal_type

    drinks = Meal.query.filter(
        Meal.meal_type == 'напиток',
        Meal.is_available == True
    ).all()

    available_meals = []
    all_meals = Meal.query.filter(
        Meal.meal_type == meal_type,
        Meal.is_available == True
    ).all()

    for meal in all_meals:
        available_quantity = meal.get_available_quantity()
        if available_quantity >= 1:
            available_meals.append(meal)

    if available_meals:
        form.meal_id.choices = [(m.id, f"{m.name} ({m.price} руб.) - {m.get_available_quantity()} порций доступно") for
                                m in available_meals]
    else:
        form.meal_id.choices = [(0, 'Нет доступных блюд для этого типа питания')]

    today = date.today()
    active_subscription = Subscription.query.filter(
        Subscription.user_id == current_user.id,
        Subscription.is_active == True,
        Subscription.start_date <= today,
        Subscription.end_date >= today,
        Subscription.meal_type == meal_type
    ).first()

    today_orders_with_subscription = Order.query.filter(
        Order.user_id == current_user.id,
        Order.meal_date == today,
        Order.meal_type == meal_type,
        Order.payment_method == 'абонемент'
    ).count()

    can_use_subscription_today = False
    if active_subscription:
        if active_subscription.used_meals < active_subscription.meals_per_week:
            if today_orders_with_subscription < 1:
                can_use_subscription_today = True

    if form.validate_on_submit():
        meal = Meal.query.get(form.meal_id.data)
        drink_id = request.form.get('drink_id')

        if not meal or meal.id == 0:
            flash('Блюдо не найдено.', 'danger')
            return redirect(url_for('order', type=meal_type))

        available_quantity = meal.get_available_quantity()
        if available_quantity < 1:
            flash(f'Блюдо "{meal.name}" временно недоступно. Нет приготовленных порций.', 'danger')
            return redirect(url_for('order', type=meal_type))

        drink = None
        if drink_id and drink_id != '':
            drink = Meal.query.get(drink_id)
            if not drink or not drink.is_available:
                flash('Напиток не найден или недоступен.', 'danger')
                return redirect(url_for('order', type=meal_type))

        meal_price = meal.price
        drink_price = drink.price if drink else 0
        total_price = meal_price + drink_price

        payment_method = form.payment_method.data

        if payment_method == 'разовая' and current_user.balance < total_price:
            flash(f'Недостаточно средств на балансе. Нужно: {total_price} руб., есть: {current_user.balance} руб.',
                  'danger')
            return redirect(url_for('add_balance'))

        if payment_method == 'абонемент':
            if not can_use_subscription_today:
                flash('Нельзя использовать абонемент. Либо его нет, либо вы уже использовали его сегодня.', 'danger')
                return redirect(url_for('order', type=meal_type))
            total_price = 0

        prepared_meal = None
        prepared_options = []

        for prepared in meal.prepared_instances:
            if prepared.expiry_date and prepared.expiry_date >= today and prepared.quantity > 0:
                days_until_expiry = (prepared.expiry_date - today).days
                prepared_options.append({
                    'prepared': prepared,
                    'days_until_expiry': days_until_expiry,
                    'expiry_date': prepared.expiry_date
                })

        if prepared_options:
            prepared_options.sort(key=lambda x: x['days_until_expiry'])
            prepared_meal = prepared_options[0]['prepared']

        if not prepared_meal:
            flash(f'Блюдо "{meal.name}" временно недоступно. Нет приготовленных порций.', 'danger')
            return redirect(url_for('order', type=meal_type))

        order_record = Order(
            user_id=current_user.id,
            meal_id=meal.id,
            meal_date=form.meal_date.data,
            meal_type=meal_type,
            total_price=0 if payment_method == 'абонемент' else meal_price,
            payment_method=payment_method,
            status='pending' if payment_method == 'разовая' else 'paid',
            notes=f'Приготовленная порция: #{prepared_meal.id} (срок годности: {prepared_meal.expiry_date.strftime("%d.%m.%Y")})'
        )

        db.session.add(order_record)
        db.session.flush()

        prepared_meal.quantity -= 1

        if drink:
            drink_order = Order(
                user_id=current_user.id,
                meal_id=drink.id,
                meal_date=form.meal_date.data,
                meal_type='напиток',
                total_price=0 if payment_method == 'абонемент' else drink_price,
                payment_method=payment_method,
                status='pending' if payment_method == 'разовая' else 'paid',
                notes=f'Дополнение к заказу #{order_record.id} ({meal_type})'
            )
            db.session.add(drink_order)

        if payment_method == 'абонемент' and active_subscription:
            active_subscription.used_meals += 1

            if active_subscription.used_meals >= active_subscription.meals_per_week:
                active_subscription.is_active = False
                flash('Вы использовали все приемы пищи по абонементу на этой неделе.', 'warning')

        if payment_method == 'разовая':
            current_user.balance -= total_price

        meal_names = meal.name
        if drink:
            meal_names += f" + {drink.name}"

        payment_text = 'бесплатно по абонементу' if payment_method == 'абонемент' else f'{total_price} руб.'
        notification = Notification(
            user_id=current_user.id,
            title='Новый заказ',
            message=f'Вы заказали {meal_names} на {form.meal_date.data.strftime("%d.%m.%Y")} ({payment_text})',
            type='заказ'
        )
        db.session.add(notification)

        chef_notification = Notification(
            user_id=1,
            title='Новый заказ',
            message=f'Ученик {current_user.username} заказал {meal.name} на {form.meal_date.data.strftime("%d.%m.%Y")}',
            type='система'
        )
        db.session.add(chef_notification)

        if prepared_meal.quantity == 1:
            low_stock_notification = Notification(
                user_id=1,
                title='Низкий запас порций',
                message=f'Осталась 1 порция {meal.name} (приготовление #{prepared_meal.id})',
                type='система'
            )
            db.session.add(low_stock_notification)

        db.session.commit()

        if payment_method == 'абонемент':
            flash('Заказ успешно создан! Бесплатно по абонементу (блюдо и напиток включены).', 'success')
        else:
            flash(f'Заказ успешно создан! Сумма: {total_price} руб.', 'success')

        return redirect(url_for('student_dashboard'))

    form.meal_date.data = date.today()

    payment_methods = [('разовая', 'Разовая оплата')]
    if can_use_subscription_today:
        payment_methods.append(('абонемент', 'Абонемент (блюдо + напиток бесплатно)'))

    meals_with_info = []
    for meal in available_meals:
        prepared_info = meal.get_prepared_meals_info()
        meals_with_info.append({
            'meal': meal,
            'available_quantity': meal.get_available_quantity(),
            'prepared_info': prepared_info
        })

    return render_template('order.html',
                           form=form,
                           date=date,
                           meal_type=meal_type,
                           active_subscription=active_subscription,
                           can_use_subscription_today=can_use_subscription_today,
                           today_orders_with_subscription=today_orders_with_subscription,
                           available_meals=available_meals,
                           meals_with_info=meals_with_info,
                           drinks=drinks,
                           payment_methods=payment_methods,
                           today=date.today())


@app.route('/allergy/<int:allergy_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['ученик'])
def edit_allergy(allergy_id):
    allergy = Allergy.query.get_or_404(allergy_id)

    if allergy.user_id != current_user.id:
        flash('Это не ваша аллергия.', 'danger')
        return redirect(url_for('allergies'))

    form = AllergyForm(obj=allergy)

    if form.validate_on_submit():
        allergy.allergen = form.allergen.data
        allergy.severity = form.severity.data
        allergy.notes = form.notes.data

        db.session.commit()
        flash('Аллергия обновлена!', 'success')
        return redirect(url_for('allergies'))

    return render_template('edit_allergy.html', form=form, allergy=allergy)


@app.route('/allergy/<int:allergy_id>/delete')
@login_required
@role_required(['ученик'])
def delete_allergy(allergy_id):
    allergy = Allergy.query.get_or_404(allergy_id)

    if allergy.user_id != current_user.id:
        flash('Это не ваша аллергия.', 'danger')
        return redirect(url_for('allergies'))

    db.session.delete(allergy)
    db.session.commit()

    flash('Аллергия удалена!', 'success')
    return redirect(url_for('allergies'))


@app.route('/receive_order/<int:order_id>')
@login_required
@role_required(['ученик'])
def receive_order(order_id):
    order = Order.query.get_or_404(order_id)

    if order.user_id != current_user.id:
        flash('Это не ваш заказ.', 'danger')
        return redirect(url_for('student_dashboard'))

    if order.status != 'paid':
        flash('Этот заказ еще не оплачен.', 'warning')
        return redirect(url_for('student_dashboard'))

    if order.is_served:
        flash('Этот заказ уже получен.', 'warning')
        return redirect(url_for('student_dashboard'))

    order.is_served = True
    order.served_at = datetime.utcnow()
    order.status = 'served'

    notification = Notification(
        user_id=current_user.id,
        title='Питание получено',
        message=f'Вы получили ваш {order.meal_type} ({order.meal.name})',
        type='система'
    )
    db.session.add(notification)

    db.session.commit()

    flash('Заказ отмечен как полученный!', 'success')
    return redirect(url_for('student_dashboard'))


@app.route('/pay_order/<int:order_id>')
@login_required
@role_required(['ученик'])
def pay_order(order_id):
    order = Order.query.get_or_404(order_id)

    if order.user_id != current_user.id:
        flash('Это не ваш заказ.', 'danger')
        return redirect(url_for('student_dashboard'))

    if order.status != 'pending':
        flash('Этот заказ уже оплачен или отменен.', 'warning')
        return redirect(url_for('student_dashboard'))

    if current_user.balance < order.total_price:
        flash('Недостаточно средств на балансе.', 'danger')
        return redirect(url_for('add_balance'))

    current_user.balance -= order.total_price
    order.status = 'paid'
    order.payment_date = datetime.utcnow()

    notification = Notification(
        user_id=current_user.id,
        title='Заказ оплачен',
        message=f'Заказ #{order.id} ({order.meal.name}) оплачен на сумму {order.total_price} руб.',
        type='оплата'
    )
    db.session.add(notification)

    db.session.commit()

    flash(f'Заказ успешно оплачен! Списано {order.total_price} руб.', 'success')
    return redirect(url_for('student_dashboard'))


@app.route('/buy_subscription', methods=['GET', 'POST'])
@login_required
@role_required(['ученик'])
def buy_subscription():
    form = SubscriptionForm()

    if form.validate_on_submit():
        meal_type = form.meal_type.data
        weeks = form.weeks.data

        today = date.today()
        active_subscription_same_type = Subscription.query.filter(
            Subscription.user_id == current_user.id,
            Subscription.meal_type == meal_type,
            Subscription.is_active == True,
            Subscription.end_date >= today
        ).first()

        if active_subscription_same_type:
            days_left = (active_subscription_same_type.end_date - today).days

            flash(
                f'У вас уже есть активный абонемент на {meal_type}, который действует до '
                f'{active_subscription_same_type.end_date.strftime("%d.%m.%Y")} '
                f'(осталось {days_left} дней). '
                f'Пожалуйста, дождитесь окончания текущего абонемента перед покупкой нового.',
                'danger'
            )
            return redirect(url_for('buy_subscription'))

        base_prices = {
            'завтрак': 200,
            'обед': 350
        }

        total_price = base_prices.get(meal_type, 200) * weeks

        if current_user.balance < total_price:
            flash(f'Недостаточно средств. Нужно: {total_price} руб., на балансе: {current_user.balance} руб.', 'danger')
            return redirect(url_for('add_balance'))

        subscription = Subscription(
            user_id=current_user.id,
            meal_type=meal_type,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7 * weeks),
            meals_per_week=5,
            used_meals=0,
            is_active=True
        )

        current_user.balance -= total_price

        db.session.add(subscription)

        notification = Notification(
            user_id=current_user.id,
            title='Абонемент куплен',
            message=f'Вы купили абонемент на {meal_type} на {weeks} недель за {total_price} руб.',
            type='оплата'
        )
        db.session.add(notification)

        db.session.commit()

        flash(f'Абонемент успешно куплен за {total_price} руб.!', 'success')
        return redirect(url_for('student_dashboard'))

    subscriptions = Subscription.query.filter(Subscription.user_id == current_user.id).all()

    active_subscriptions_info = {}
    today = date.today()

    for meal_type in ['завтрак', 'обед']:
        active_sub = Subscription.query.filter(
            Subscription.user_id == current_user.id,
            Subscription.meal_type == meal_type,
            Subscription.is_active == True,
            Subscription.end_date >= today
        ).first()

        if active_sub:
            days_left = (active_sub.end_date - today).days
            active_subscriptions_info[meal_type] = {
                'exists': True,
                'end_date': active_sub.end_date.strftime("%d.%m.%Y"),
                'days_left': days_left,
                'used_meals': active_sub.used_meals,
                'meals_per_week': active_sub.meals_per_week
            }
        else:
            active_subscriptions_info[meal_type] = {'exists': False}

    return render_template('buy_subscription.html',
                           form=form,
                           subscriptions=subscriptions,
                           date=date,
                           active_subscriptions_info=active_subscriptions_info)


@app.route('/chef')
@login_required
@role_required(['повар'])
def chef_dashboard():
    today = date.today()

    today_orders = Order.query.filter(Order.meal_date == today).all()

    orders_with_allergies = []
    for order in today_orders:
        user_allergies = Allergy.query.filter(Allergy.user_id == order.user_id).all()
        allergen_list = [allergy.allergen for allergy in user_allergies]

        orders_with_allergies.append({
            'order': order,
            'user': order.user,
            'allergens': ', '.join(allergen_list) if allergen_list else 'нет'
        })

    pending_orders = len([o for o in today_orders if o.status == 'pending'])
    paid_orders = len([o for o in today_orders if o.status == 'paid'])
    served_orders = len([o for o in today_orders if o.status == 'served'])

    seven_days_ago = today - timedelta(days=7)

    recent_orders = Order.query.filter(
        Order.meal_date >= seven_days_ago,
        Order.meal_date <= today,
        Order.status == 'served'
    ).all()

    breakfast_count = len([o for o in recent_orders if o.meal_type == 'завтрак'])
    lunch_count = len([o for o in recent_orders if o.meal_type == 'обед'])

    from collections import Counter
    meal_counter = Counter()
    for order in recent_orders:
        if order.meal:
            meal_counter[order.meal.name] += 1

    popular_meals = meal_counter.most_common(5)

    all_meals = Meal.query.filter(Meal.is_available == True).all()
    all_meals_info = []
    available_meals = []
    low_stock_meals = []
    unavailable_meals = []

    for meal in all_meals:
        available_quantity = meal.get_available_quantity()
        prepared_info = meal.get_prepared_meals_info()

        meal_info = {
            'meal': meal,
            'available_quantity': available_quantity,
            'prepared_info': prepared_info
        }
        all_meals_info.append(meal_info)

        if available_quantity >= 1:
            available_meals.append(meal)
        if available_quantity == 0:
            unavailable_meals.append(meal)
        elif available_quantity <= 2:
            low_stock_meals.append(meal)

    return render_template('chef_dashboard.html',
                           orders_with_allergies=orders_with_allergies,
                           pending_orders=pending_orders,
                           paid_orders=paid_orders,
                           served_orders=served_orders,
                           breakfast_count=breakfast_count,
                           lunch_count=lunch_count,
                           popular_meals=popular_meals,
                           all_meals_info=all_meals_info,
                           available_meals=available_meals,
                           low_stock_meals=low_stock_meals,
                           unavailable_meals=unavailable_meals,
                           today=today)


@app.route('/prepare_meal', methods=['GET', 'POST'])
@login_required
@role_required(['повар'])
def prepare_meal():
    form = PrepareMealForm()

    available_meals = Meal.query.filter(Meal.is_available == True).all()
    inventory_items = Inventory.query.all()

    if available_meals:
        form.meal_id.choices = [(m.id, f"{m.name} ({m.price} руб.)") for m in available_meals]
    else:
        form.meal_id.choices = [(0, 'Нет доступных блюд')]

    if form.validate_on_submit():
        meal = Meal.query.get(form.meal_id.data)
        portions = form.quantity.data

        if not meal:
            flash('Блюдо не найдено.', 'danger')
            return redirect(url_for('prepare_meal'))

        if portions <= 0 or portions > 100:
            flash('Некорректное количество порций.', 'danger')
            return redirect(url_for('prepare_meal'))

        missing_ingredients = []
        can_prepare = True

        if not hasattr(meal, 'meal_ingredients') or not meal.meal_ingredients:
            flash(f'Для блюда "{meal.name}" не указаны ингредиенты.', 'danger')
            return redirect(url_for('prepare_meal'))

        for mi in meal.meal_ingredients:
            if not hasattr(mi, 'ingredient'):
                app.logger.warning(f'MealIngredient {mi.id} не имеет атрибута ingredient')
                continue

            required_amount = mi.quantity_required * portions
            if mi.ingredient.quantity < required_amount:
                can_prepare = False
                missing_ingredients.append({
                    'id': mi.ingredient.id,
                    'name': mi.ingredient.ingredient,
                    'required': required_amount,
                    'available': mi.ingredient.quantity,
                    'unit': mi.unit or mi.ingredient.unit
                })

        if not can_prepare:
            session['missing_ingredients'] = missing_ingredients
            session['meal_id'] = meal.id
            session['portions'] = portions
            session['meal_name'] = meal.name
            flash(f'Недостаточно ингредиентов для приготовления {portions} порций {meal.name}.', 'danger')
            return redirect(url_for('purchase_request'))

        ingredients_used = []
        for mi in meal.meal_ingredients:
            if hasattr(mi, 'ingredient'):
                ingredient = mi.ingredient
                required_amount = mi.quantity_required * portions

                if ingredient.quantity < required_amount:
                    flash(f'Недостаточно {ingredient.ingredient} во время приготовления.', 'danger')
                    return redirect(url_for('prepare_meal'))

                ingredients_used.append({
                    'name': ingredient.ingredient,
                    'used': required_amount,
                    'unit': mi.unit or ingredient.unit,
                    'remaining': ingredient.quantity - required_amount
                })

                ingredient.quantity -= required_amount
                ingredient.last_updated = datetime.utcnow()

        prepared_meal = PreparedMeal(
            meal_id=meal.id,
            quantity=portions,
            prepared_by=current_user.id,
            prepared_date=date.today(),
            expiry_date=form.expiry_date.data,
            notes=form.notes.data or f'Приготовлено {portions} порций'
        )

        db.session.add(prepared_meal)

        notification = Notification(
            user_id=current_user.id,
            title='Блюдо приготовлено',
            message=f'Приготовлено {portions} порций {meal.name}. Ингредиенты списаны со склада.',
            type='система'
        )
        db.session.add(notification)

        ingredients_details = []
        for ing in ingredients_used:
            ingredients_details.append(f"{ing['used']} {ing['unit']} {ing['name']}")

        detailed_notification = Notification(
            user_id=current_user.id,
            title='Детали использования ингредиентов',
            message=f'Для приготовления {portions} порций {meal.name} использовано: {", ".join(ingredients_details)}',
            type='система'
        )
        db.session.add(detailed_notification)

        db.session.commit()

        low_stock_meals = []
        for m in available_meals:
            if m.get_available_quantity() <= 2 and m.get_available_quantity() > 0:
                low_stock_meals.append(m)

        if low_stock_meals:
            low_stock_message = "Скоро закончатся порции: "
            low_stock_message += ", ".join([f"{m.name} ({m.get_available_quantity()} пор.)" for m in low_stock_meals])

            low_stock_notification = Notification(
                user_id=current_user.id,
                title='Низкий запас порций',
                message=low_stock_message,
                type='система'
            )
            db.session.add(low_stock_notification)
            db.session.commit()

        flash(f'Успешно приготовлено {portions} порций {meal.name}! Ингредиенты списаны со склада.', 'success')
        return redirect(url_for('chef_dashboard'))

    return render_template('prepare_meal.html',
                           form=form,
                           available_meals=available_meals,
                           inventory_items=inventory_items,
                           date=date)


@app.route('/api/meal/<int:meal_id>/ingredients')
@login_required
@role_required(['повар'])
def api_meal_ingredients(meal_id):
    try:
        meal = Meal.query.get_or_404(meal_id)
        portions = int(request.args.get('portions', 1))

        ingredients = []

        if hasattr(meal, 'meal_ingredients'):
            app.logger.info(f"Найдено {len(meal.meal_ingredients.all())} ингредиентов для блюда {meal.name}")

            for mi in meal.meal_ingredients:
                if hasattr(mi, 'ingredient'):
                    ingredients.append({
                        'id': mi.ingredient.id,
                        'name': mi.ingredient.ingredient,
                        'quantity_required': mi.quantity_required * portions,
                        'unit': mi.unit or mi.ingredient.unit,
                        'available': mi.ingredient.quantity,
                        'min_quantity': mi.ingredient.min_quantity
                    })
                else:
                    app.logger.warning(f"У связи MealIngredient {mi.id} нет атрибута ingredient")
        else:
            app.logger.warning(f"У блюда {meal.name} нет атрибута meal_ingredients")

        return jsonify({
            'meal_id': meal.id,
            'meal_name': meal.name,
            'portions': portions,
            'ingredients': ingredients,
            'can_prepare': meal.can_prepare(portions) if hasattr(meal, 'can_prepare') else False,
            'ingredients_count': len(ingredients)
        })

    except Exception as e:
        app.logger.error(f"Error in api_meal_ingredients: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/inventory', methods=['GET', 'POST'])
@login_required
@role_required(['повар', 'администратор'])
def inventory():
    form = InventoryForm()

    if form.validate_on_submit():
        item = Inventory.query.filter(Inventory.ingredient == form.ingredient.data).first()

        if item:
            item.quantity = form.quantity.data
            item.min_quantity = form.min_quantity.data
            item.last_updated = datetime.utcnow()
        else:
            item = Inventory(
                ingredient=form.ingredient.data,
                quantity=form.quantity.data,
                unit=form.unit.data,
                min_quantity=form.min_quantity.data
            )
            db.session.add(item)

        db.session.commit()
        flash('Инвентарь обновлен!', 'success')
        return redirect(url_for('inventory'))

    inventory_items = Inventory.query.all()
    return render_template('inventory.html', form=form, inventory=inventory_items)


@app.route('/purchase_request', methods=['GET', 'POST'])
@login_required
@role_required(['повар'])
def purchase_request():
    form = PurchaseRequestForm()

    existing_ingredients = Inventory.query.order_by(Inventory.ingredient).all()

    if existing_ingredients:
        form.ingredient_id.choices = [(i.id, f"{i.ingredient} ({i.unit}) - доступно: {i.quantity}") for i in
                                      existing_ingredients]
    else:
        form.ingredient_id.choices = [(0, 'Нет продуктов в базе')]

    missing_ingredients = session.get('missing_ingredients', [])
    meal_id = session.get('meal_id')
    portions = session.get('portions', 1)

    if missing_ingredients and meal_id:
        meal = Meal.query.get(meal_id)
    else:
        meal = None

    if form.validate_on_submit():
        ingredient = Inventory.query.get(form.ingredient_id.data)

        if not ingredient:
            flash('Продукт не найден.', 'danger')
            return redirect(url_for('purchase_request'))

        request_item = PurchaseRequest(
            ingredient=ingredient.ingredient,
            ingredient_id=ingredient.id,
            quantity=form.quantity.data,
            unit=ingredient.unit,
            requested_by=current_user.id,
            status='на рассмотрении',
            notes=form.notes.data
        )

        if hasattr(PurchaseRequest, 'urgency'):
            request_item.urgency = form.urgency.data

        db.session.add(request_item)

        if missing_ingredients:
            session.pop('missing_ingredients', None)
            session.pop('meal_id', None)
            session.pop('portions', None)

            admin_notification = Notification(
                user_id=1,
                title='Срочная заявка на закупку',
                message=f'Повар {current_user.username} создал заявку на закупку ингредиентов для приготовления {portions} порций {meal.name if meal else "блюда"}.',
                type='система'
            )
            db.session.add(admin_notification)

        db.session.commit()

        flash('Заявка на закупку создана!', 'success')
        return redirect(url_for('chef_dashboard'))

    return render_template('purchase_request.html',
                           form=form,
                           meal=meal,
                           portions=portions,
                           missing_ingredients=missing_ingredients,
                           existing_ingredients=existing_ingredients)


@app.route('/prepared_meals')
@login_required
@role_required(['повар', 'администратор'])
def prepared_meals():
    today = date.today()
    prepared = PreparedMeal.query.filter(
        PreparedMeal.expiry_date >= today
    ).order_by(PreparedMeal.prepared_date.desc()).all()

    meals_summary = {}
    for pm in prepared:
        meal_name = pm.meal.name if hasattr(pm, 'meal') else f'Блюдо #{pm.meal_id}'
        if meal_name not in meals_summary:
            meals_summary[meal_name] = 0
        meals_summary[meal_name] += pm.quantity

    return render_template('prepared_meals.html',
                           prepared=prepared,
                           meals_summary=meals_summary,
                           today=today)


@app.route('/serve_order/<int:order_id>')
@login_required
@role_required(['повар'])
def serve_order(order_id):
    order = Order.query.get_or_404(order_id)

    if order.status != 'paid':
        flash('Этот заказ не оплачен.', 'warning')
        return redirect(url_for('chef_dashboard'))

    if order.is_served:
        flash('Этот заказ уже выдан.', 'warning')
        return redirect(url_for('chef_dashboard'))

    order.is_served = True
    order.served_at = datetime.utcnow()
    order.served_by = current_user.id
    order.status = 'served'

    notification = Notification(
        user_id=order.user_id,
        title='Питание выдано',
        message=f'Ваш {order.meal_type} ({order.meal.name}) был выдан',
        type='система'
    )
    db.session.add(notification)

    db.session.commit()
    flash('Заказ отмечен как выданный.', 'success')
    return redirect(url_for('chef_dashboard'))


@app.route('/admin')
@login_required
@role_required(['администратор'])
def admin_dashboard():
    today = date.today()

    stats = {
        'total_users': User.query.count(),
        'total_orders_today': Order.query.filter(Order.meal_date == today).count(),
        'total_revenue_today': db.session.query(func.sum(Order.total_price)).filter(
            Order.meal_date == today,
            Order.status == 'paid'
        ).scalar() or 0.0,
        'pending_requests': PurchaseRequest.query.filter(
            PurchaseRequest.status == 'на рассмотрении'
        ).count(),
        'total_all_orders': Order.query.count(),
        'active_meals': Meal.query.filter(Meal.is_available == True).count(),
        'students_count': User.query.filter(User.role == 'ученик').count(),
        'chefs_count': User.query.filter(User.role == 'повар').count(),
        'admins_count': User.query.filter(User.role == 'администратор').count()
    }

    return render_template('admin_dashboard.html', **stats)


@app.route('/admin/users')
@login_required
@role_required(['администратор'])
def admin_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)


@app.route('/admin/user/add', methods=['GET', 'POST'])
@login_required
@role_required(['администратор'])
def add_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'ученик')
        grade = request.form.get('grade', '')

        if not username or not email or not password:
            flash('Заполните все обязательные поля!', 'danger')
            return redirect(url_for('add_user'))

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует!', 'danger')
            return redirect(url_for('add_user'))

        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует!', 'danger')
            return redirect(url_for('add_user'))

        if len(password) < 6:
            flash('Пароль должен содержать минимум 6 символов', 'danger')
            return redirect(url_for('add_user'))

        user = User(
            username=username,
            email=email,
            role=role,
            grade=grade,
            balance=0.00
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash(f'Пользователь {username} успешно добавлен!', 'success')
        return redirect(url_for('admin_users'))

    return render_template('add_user.html')


@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(['администратор'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'ученик')
        grade = request.form.get('grade', '')
        balance = float(request.form.get('balance', 0))

        if username != user.username and User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует!', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))

        if email != user.email and User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует!', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))

        user.username = username
        user.email = email
        user.role = role
        user.grade = grade
        user.balance = balance

        db.session.commit()

        flash(f'Пользователь {username} успешно обновлен!', 'success')
        return redirect(url_for('admin_users'))

    orders_count = Order.query.filter_by(user_id=user.id).count()
    feedbacks_count = Feedback.query.filter_by(user_id=user.id).count()
    allergies_count = Allergy.query.filter_by(user_id=user.id).count()

    return render_template('edit_user.html',
                           user=user,
                           orders_count=orders_count,
                           feedbacks_count=feedbacks_count,
                           allergies_count=allergies_count)


@app.route('/admin/user/<int:user_id>/delete')
@login_required
@role_required(['администратор'])
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Вы не можете удалить себя!', 'danger')
        return redirect(url_for('admin_users'))

    user = User.query.get_or_404(user_id)
    username = user.username

    Allergy.query.filter_by(user_id=user_id).delete()
    Feedback.query.filter_by(user_id=user_id).delete()
    Notification.query.filter_by(user_id=user_id).delete()
    Subscription.query.filter_by(user_id=user_id).delete()

    Order.query.filter_by(user_id=user_id).update({'user_id': None})

    db.session.delete(user)
    db.session.commit()

    flash(f'Пользователь {username} удален!', 'success')
    return redirect(url_for('admin_users'))


@app.route('/statistics')
@login_required
@role_required(['администратор'])
def statistics():
    dates = []
    revenue_data = []
    orders_data = []

    for i in range(6, -1, -1):
        day = date.today() - timedelta(days=i)
        dates.append(day.strftime('%d.%m'))

        revenue = db.session.query(func.sum(Order.total_price)).filter(
            Order.meal_date == day,
            Order.status == 'paid'
        ).scalar() or 0
        revenue_data.append(float(revenue))

        orders = Order.query.filter(Order.meal_date == day).count()
        orders_data.append(orders)

    popular_meals = db.session.query(
        Meal.name,
        func.count(Order.id).label('orders_count')
    ).join(Order).group_by(Meal.id).order_by(func.count(Order.id).desc()).limit(5).all()

    return render_template('statistics.html',
                           dates=dates,
                           revenue_data=revenue_data,
                           orders_data=orders_data,
                           popular_meals=popular_meals)


@app.route('/reports')
@login_required
@role_required(['администратор'])
def reports():
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    total_users = User.query.count()
    total_meals = Meal.query.count()
    total_orders = Order.query.filter(
        Order.status.in_(['paid', 'served'])
    ).count()
    total_revenue = db.session.query(func.sum(Order.total_price)).filter(
        Order.status.in_(['paid', 'served'])
    ).scalar() or 0

    weekly_orders = db.session.query(
        Meal.name,
        func.count(Order.id).label('sold_count'),
        func.sum(Order.total_price).label('revenue')
    ).join(Order).filter(
        Order.meal_date >= start_of_week,
        Order.meal_date <= end_of_week,
        Order.status.in_(['paid', 'served']),
        Order.meal_type.in_(['завтрак', 'обед'])
    ).group_by(Meal.id).order_by(func.count(Order.id).desc()).all()

    total_weekly_sales = sum(order.sold_count for order in weekly_orders)
    total_weekly_revenue = sum(float(order.revenue or 0) for order in weekly_orders)

    spoiled_meals = db.session.query(
        Meal.name,
        func.sum(PreparedMeal.quantity).label('spoiled_count')
    ).join(PreparedMeal).filter(
        PreparedMeal.expiry_date >= start_of_week,
        PreparedMeal.expiry_date <= end_of_week,
        PreparedMeal.quantity > 0
    ).group_by(Meal.id).all()

    total_spoiled = sum(meal.spoiled_count for meal in spoiled_meals)

    weekly_purchases = db.session.query(
        PurchaseRequest.ingredient,
        PurchaseRequest.quantity,
        PurchaseRequest.unit,
        PurchaseRequest.notes,
        PurchaseRequest.status
    ).filter(
        PurchaseRequest.requested_at >= start_of_week,
        PurchaseRequest.requested_at <= end_of_week + timedelta(days=1),
        PurchaseRequest.status == 'одобрена'
    ).all()

    purchase_summary = {}
    for purchase in weekly_purchases:
        key = f"{purchase.ingredient} ({purchase.unit})"
        if key not in purchase_summary:
            purchase_summary[key] = 0
        purchase_summary[key] += purchase.quantity

    weekly_subscriptions = db.session.query(
        Subscription.meal_type,
        func.count(Subscription.id).label('count'),
        func.sum(
            case(
                (Subscription.meal_type == 'завтрак', 200),
                (Subscription.meal_type == 'обед', 350),
                else_=0
            ) *
            (extract('day', Subscription.end_date - Subscription.start_date) / 7)
        ).label('revenue')
    ).filter(
        Subscription.start_date >= start_of_week,
        Subscription.start_date <= end_of_week
    ).group_by(Subscription.meal_type).all()

    total_subscriptions_count = sum(sub.count for sub in weekly_subscriptions)
    total_subscriptions_revenue = sum(float(sub.revenue or 0) for sub in weekly_subscriptions)

    popular_meals = db.session.query(
        Meal.name,
        func.count(Order.id).label('orders_count')
    ).join(Order).filter(
        Order.status.in_(['paid', 'served'])
    ).group_by(Meal.id).order_by(func.count(Order.id).desc()).limit(5).all()

    daily_stats = []
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        day_name = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][i]

        orders_count = Order.query.filter(
            Order.meal_date == day,
            Order.status.in_(['paid', 'served'])
        ).count()

        daily_revenue = db.session.query(func.sum(Order.total_price)).filter(
            Order.meal_date == day,
            Order.status.in_(['paid', 'served'])
        ).scalar() or 0

        daily_stats.append({
            'day': day_name,
            'date': day.strftime('%d.%m'),
            'orders': orders_count,
            'revenue': float(daily_revenue)
        })

    return render_template('reports.html',
                           total_users=total_users,
                           total_meals=total_meals,
                           total_orders=total_orders,
                           total_revenue=total_revenue,

                           start_of_week=start_of_week.strftime('%d.%m.%Y'),
                           end_of_week=end_of_week.strftime('%d.%m.%Y'),

                           weekly_orders=weekly_orders,
                           total_weekly_sales=total_weekly_sales,
                           total_weekly_revenue=total_weekly_revenue,

                           spoiled_meals=spoiled_meals,
                           total_spoiled=total_spoiled,

                           purchase_summary=purchase_summary,
                           weekly_purchases=weekly_purchases,

                           weekly_subscriptions=weekly_subscriptions,
                           total_subscriptions_count=total_subscriptions_count,
                           total_subscriptions_revenue=total_subscriptions_revenue,

                           popular_meals=popular_meals,

                           daily_stats=daily_stats,

                           today=today)


@app.route('/manage_requests')
@login_required
@role_required(['администратор'])
def manage_requests():
    purchase_requests = PurchaseRequest.query.order_by(
        PurchaseRequest.requested_at.desc()
    ).all()

    for req in purchase_requests:
        if req.requested_by:
            req.requested_by_user = User.query.get(req.requested_by)
        if req.approved_by:
            req.approved_by_user = User.query.get(req.approved_by)

    return render_template('manage_requests.html', purchase_requests=purchase_requests)


@app.route('/approve_request/<int:request_id>')
@login_required
@role_required(['администратор'])
def approve_request(request_id):
    purchase_request = PurchaseRequest.query.get_or_404(request_id)

    if purchase_request.status != 'на рассмотрении':
        flash('Эта заявка уже обработана.', 'warning')
        return redirect(url_for('manage_requests'))

    purchase_request.status = 'одобрена'
    purchase_request.approved_by = current_user.id
    purchase_request.approved_at = datetime.utcnow()

    if purchase_request.ingredient_id:
        inventory_item = Inventory.query.get(purchase_request.ingredient_id)
    else:
        inventory_item = Inventory.query.filter(
            Inventory.ingredient == purchase_request.ingredient
        ).first()

    if inventory_item:
        inventory_item.quantity += purchase_request.quantity
        inventory_item.last_updated = datetime.utcnow()
    else:
        inventory_item = Inventory(
            ingredient=purchase_request.ingredient,
            quantity=purchase_request.quantity,
            unit=purchase_request.unit or 'шт',
            min_quantity=purchase_request.quantity * 0.2
        )
        db.session.add(inventory_item)

    if purchase_request.requested_by:
        notification = Notification(
            user_id=purchase_request.requested_by,
            title='Заявка одобрена',
            message=f'Ваша заявка на {purchase_request.ingredient} одобрена. Продукты добавлены на склад.',
            type='система'
        )
        db.session.add(notification)

    db.session.commit()
    flash('Заявка одобрена и инвентарь пополнен!', 'success')
    return redirect(url_for('manage_requests'))


@app.route('/use_ingredient', methods=['POST'])
@login_required
@role_required(['повар', 'администратор'])
def use_ingredient():
    ingredient_id = request.form.get('ingredient_id')
    amount = float(request.form.get('amount', 0))

    if not ingredient_id or amount <= 0:
        flash('Некорректные данные.', 'danger')
        return redirect(url_for('inventory'))

    ingredient = Inventory.query.get_or_404(ingredient_id)

    if ingredient.quantity < amount:
        flash(
            f'Недостаточно {ingredient.ingredient}. Доступно: {ingredient.quantity} {ingredient.unit}, требуется: {amount} {ingredient.unit}.',
            'danger')
        return redirect(url_for('inventory'))

    ingredient.quantity -= amount
    ingredient.last_updated = datetime.utcnow()

    notification = Notification(
        user_id=current_user.id,
        title='Использован ингредиент',
        message=f'Использовано {amount} {ingredient.unit} {ingredient.ingredient}. Остаток: {ingredient.quantity} {ingredient.unit}.',
        type='система'
    )
    db.session.add(notification)

    db.session.commit()

    flash(f'Использовано {amount} {ingredient.unit} {ingredient.ingredient}.', 'success')
    return redirect(url_for('inventory'))


@app.route('/reject_request/<int:request_id>')
@login_required
@role_required(['администратор'])
def reject_request(request_id):
    purchase_request = PurchaseRequest.query.get_or_404(request_id)

    if purchase_request.status != 'на рассмотрении':
        flash('Эта заявка уже обработана.', 'warning')
        return redirect(url_for('manage_requests'))

    purchase_request.status = 'отклонена'
    purchase_request.approved_by = current_user.id
    purchase_request.approved_at = datetime.utcnow()

    if purchase_request.requested_by:
        notification = Notification(
            user_id=purchase_request.requested_by,
            title='Заявка отклонена',
            message=f'Ваша заявка на {purchase_request.ingredient} отклонена.',
            type='система'
        )
        db.session.add(notification)

    db.session.commit()
    flash('Заявка отклонена!', 'success')
    return redirect(url_for('manage_requests'))

# Маршрут для самой страницы с картой
@app.route('/map')
@login_required
def show_map():
    return render_template('map.html')


@app.route('/api/v1/canteens', methods=['GET'])
def get_canteens():
    # Получаем координаты из параметров запроса (URL)
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    radius = 2500  # Радиус поиска в метрах

    if not lat or not lon:
        return jsonify({"error": "Coordinates are required"}), 400

    overpass_url = "https://overpass-api.de/api/interpreter"

    # Ищем столовые (canteen), кафе (cafe) и рестораны (restaurant)
    overpass_query = f"""
    [out:json];
    (
      node["amenity"~"canteen|restaurant|cafe"](around:{radius},{lat},{lon});
      way["amenity"~"canteen|restaurant|cafe"](around:{radius},{lat},{lon});
    );
    out center;
    """

    try:
        response = requests.get(overpass_url, params={'data': overpass_query}, timeout=10)
        data = response.json()

        results = []
        for element in data.get('elements', []):
            e_lat = element.get('lat') or element.get('center', {}).get('lat')
            e_lon = element.get('lon') or element.get('center', {}).get('lon')
            tags = element.get('tags', {})

            results.append({
                "name": tags.get('name', 'Точка питания'),
                "address": tags.get('addr:street', 'Адрес не указан'),
                "lat": e_lat,
                "lon": e_lon,
                "cuisine": tags.get('cuisine', 'Общепит')
            })
        return jsonify(results)
    except Exception as e:
        return jsonify([])


if __name__ == '__main__':
    create_tables()
    app.run(debug=True, port=8080)