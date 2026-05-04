from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class RegisterForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=4, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Подтвердите пароль', validators=[
        DataRequired(),
        EqualTo('password', message='Пароли не совпадают.')
    ])
    submit = SubmitField('Зарегистрироваться')

class UploadForm(FlaskForm):
    folder_id = SelectField(
        'Папка',
        coerce=int,
        choices=[(0, 'Корневая папка')],
        # validators=[DataRequired()]  # ❌ Убрана валидация
    )
    submit = SubmitField('Загрузить')

    def set_folder_choices(self, user_id):
        from models import Folder
        if user_id:
            folders = Folder.query.filter_by(user_id=user_id).all()
            self.folder_id.choices = [(f.id, f.name) for f in folders]
            # Добавляем корневую папку, если её нет в списке
            if (0, 'Корневая папка') not in self.folder_id.choices:
                self.folder_id.choices.insert(0, (0, 'Корневая папка'))
        else:
            self.folder_id.choices = [(0, 'Корневая папка')]