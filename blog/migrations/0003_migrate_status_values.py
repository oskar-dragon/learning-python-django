from django.db import migrations


def migrate_status_values(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    Post.objects.filter(status="DF").update(status="draft")
    Post.objects.filter(status="PB").update(status="published")


def reverse_status_values(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    Post.objects.filter(status="draft").update(status="DF")
    Post.objects.filter(status="published").update(status="PB")


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0002_alter_status_field"),
    ]

    operations = [
        migrations.RunPython(migrate_status_values, reverse_status_values),
    ]
