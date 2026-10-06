import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from rest_framework.authtoken.models import Token

from plan.constants import GROUP_FACTORY_MANAGER, GROUP_FACTORY_REPRESENTATIVE
from plan.models import Factory, FactoryUser


class Command(BaseCommand):
    help = "Create demo factories, users, groups and tokens (idempotent). Demo only!"

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        password = os.environ.get("DEMO_PASSWORD", "demo12345")

        north, _ = Factory.objects.get_or_create(name="ЗМК Север")
        south, _ = Factory.objects.get_or_create(name="ЗМК Юг")

        rep_group, _ = Group.objects.get_or_create(name=GROUP_FACTORY_REPRESENTATIVE)
        mgr_group, _ = Group.objects.get_or_create(name=GROUP_FACTORY_MANAGER)

        specs = [("rep", rep_group), ("manager", mgr_group), ("nobody", None)]
        rows = []
        for username, group in specs:
            user, _ = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.save()
            user.groups.set([group] if group else [])
            token, _ = Token.objects.get_or_create(user=user)
            rows.append((user, token))

        FactoryUser.objects.get_or_create(user=rows[0][0], factory=north)

        self.stdout.write(f"Factories: {north.name}={north.pk}, {south.name}={south.pk}")
        self.stdout.write(f"{'username':<10}{'user_id':<9}{'token':<42}factory ids")
        for user, token in rows:
            ids = list(user.factory_links.values_list("factory_id", flat=True))
            if user.groups.filter(name=GROUP_FACTORY_MANAGER).exists():
                ids = "all"
            self.stdout.write(f"{user.username:<10}{user.pk:<9}{token.key:<42}{ids}")
