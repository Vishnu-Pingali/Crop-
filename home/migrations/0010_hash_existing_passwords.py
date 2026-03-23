from django.contrib.auth.hashers import make_password
from django.db import migrations


def _is_hashed(value: str) -> bool:
    return bool(value) and value.startswith(('pbkdf2_', 'argon2$', 'bcrypt$', 'scrypt$'))


def hash_existing_passwords(apps, schema_editor):
    UserProfile = apps.get_model('home', 'userProfile')
    for user in UserProfile.objects.all():
        updated_fields = []
        if user.password and not _is_hashed(user.password):
            user.password = make_password(user.password)
            updated_fields.append('password')
        if user.confirm_password:
            user.confirm_password = ''
            updated_fields.append('confirm_password')
        if updated_fields:
            user.save(update_fields=updated_fields)


class Migration(migrations.Migration):
    dependencies = [
        ('home', '0009_voiceconversationsession_voiceconversationturn'),
    ]

    operations = [
        migrations.RunPython(hash_existing_passwords, migrations.RunPython.noop),
    ]
