from django import forms

class PersonalInfoForm(forms.Form):
    first_name = forms.CharField(label='Ad', max_length=100)
    last_name = forms.CharField(label='Soyad', max_length=100)
    email = forms.EmailField(label='E-posta')

class EducationForm(forms.Form):
    school = forms.CharField(label='Okul Adı', max_length=200)
    degree = forms.CharField(label='Derece/Bölüm', max_length=100)
    graduation_year = forms.IntegerField(label='Mezuniyet Yılı')

class ExperienceForm(forms.Form):
    company = forms.CharField(label='Şirket Adı', max_length=200)
    position = forms.CharField(label='Pozisyon', max_length=100)
    years = forms.IntegerField(label='Çalışma Süresi (yıl)')
