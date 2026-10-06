import json

import pytest
from rest_framework.authtoken.models import Token

from plan.models import WorkVolume

URL = "/work-volume-list/"
pytestmark = pytest.mark.django_db


def post(client, user, body, **kw):
    if user is not None:
        client.force_authenticate(user)
    return client.post(URL, data=body, format="json", **kw)


def body_for(payload, user, **ov):
    return payload(author=user.pk, **ov)


def assert_error(resp, status, code):
    assert resp.status_code == status, resp.content
    data = resp.json()
    assert data["errorCode"] == code
    assert isinstance(data["message"], str)
    assert isinstance(data["details"], dict)


def test_unauthenticated(api_client, payload):
    resp = api_client.post(URL, data=payload(), format="json")
    assert_error(resp, 401, 900)
    assert "WWW-Authenticate" in resp


def test_get_not_allowed(api_client, manager_user):
    api_client.force_authenticate(manager_user)
    assert_error(api_client.get(URL), 405, 905)


def test_body_array(api_client, manager_user):
    assert_error(post(api_client, manager_user, [1, 2]), 400, 901)


def test_broken_json(api_client, manager_user):
    api_client.force_authenticate(manager_user)
    resp = api_client.post(URL, data="{bad", content_type="application/json")
    assert_error(resp, 400, 901)


def test_text_plain(api_client, manager_user):
    api_client.force_authenticate(manager_user)
    resp = api_client.post(URL, data="x", content_type="text/plain")
    assert_error(resp, 415, 906)


def test_empty_body(api_client, manager_user):
    resp = post(api_client, manager_user, {})
    assert_error(resp, 406, 279)
    assert set(resp.json()["details"]["missing"]) == {
        "factory",
        "start",
        "finish",
        "weight",
        "author",
    }


def test_null_field(api_client, manager_user, payload):
    resp = post(api_client, manager_user, body_for(payload, manager_user, start=None))
    assert_error(resp, 406, 279)
    assert resp.json()["details"]["missing"] == ["start"]


@pytest.mark.parametrize("ov", [{"factory": "1"}, {"weight": True}, {"weight": 1.5}])
def test_wrong_types(api_client, manager_user, payload, ov):
    assert_error(post(api_client, manager_user, body_for(payload, manager_user, **ov)), 400, 901)


@pytest.mark.parametrize(
    "ov",
    [
        {"start": 1738281600, "finish": 1735689600},
        {"weight": -1},
        {"start": 1735689601},
        {"start": 1735689600000},
    ],
)
def test_wrong_values(api_client, manager_user, payload, ov):
    assert_error(post(api_client, manager_user, body_for(payload, manager_user, **ov)), 400, 901)


@pytest.mark.parametrize("who", ["nobody_user", "manager_user", "rep_user"])
def test_unknown_factory(api_client, payload, fake_tsdb, request, who):
    user = request.getfixturevalue(who)
    resp = post(api_client, user, body_for(payload, user, factory=99999))
    assert_error(resp, 404, 174)


def test_author_mismatch(api_client, manager_user, payload, fake_tsdb):
    resp = post(api_client, manager_user, payload(author=manager_user.pk + 100))
    assert_error(resp, 403, 903)
    assert WorkVolume.objects.count() == 0 and fake_tsdb == []


def test_nobody(api_client, nobody_user, payload, fake_tsdb):
    assert_error(post(api_client, nobody_user, body_for(payload, nobody_user)), 403, 902)


def test_manager_creates(api_client, manager_user, factory_a, payload, fake_tsdb):
    resp = post(api_client, manager_user, body_for(payload, manager_user))
    assert resp.status_code == 201
    wv = WorkVolume.objects.get()
    data = resp.json()
    assert data["id"] == wv.pk and data["factory"] == factory_a.pk
    assert data["start"] == 1735689600 and data["finish"] == 1738281600
    assert data["weight"] == 1500 and "created" in data
    assert len(fake_tsdb) == 1
    rec = fake_tsdb[0]
    assert rec.factory == factory_a.external_id
    assert rec.author == manager_user.pk
    assert rec.created == wv.created


def test_manager_update_same_period(api_client, manager_user, payload, fake_tsdb):
    post(api_client, manager_user, body_for(payload, manager_user))
    first = WorkVolume.objects.get()
    resp = post(api_client, manager_user, body_for(payload, manager_user, weight=7))
    assert resp.status_code == 201
    wv = WorkVolume.objects.get()
    assert wv.weight == 7 and wv.created > first.created
    assert len(fake_tsdb) == 2


def test_manager_other_factory(api_client, manager_user, factory_b, payload, fake_tsdb):
    resp = post(api_client, manager_user, body_for(payload, manager_user, factory=factory_b.pk))
    assert resp.status_code == 201


def test_rep_own_factory(api_client, rep_user, payload, fake_tsdb):
    assert post(api_client, rep_user, body_for(payload, rep_user)).status_code == 201


def test_rep_foreign_factory(api_client, rep_user, factory_b, payload, fake_tsdb):
    resp = post(api_client, rep_user, body_for(payload, rep_user, factory=factory_b.pk))
    assert_error(resp, 404, 174)
    assert WorkVolume.objects.count() == 0 and fake_tsdb == []


def test_both_roles(api_client, both_roles_user, factory_b, payload, fake_tsdb):
    resp = post(
        api_client, both_roles_user, body_for(payload, both_roles_user, factory=factory_b.pk)
    )
    assert resp.status_code == 201


def test_overlapping_period_creates_second(api_client, manager_user, payload, fake_tsdb):
    post(api_client, manager_user, body_for(payload, manager_user))
    resp = post(api_client, manager_user, body_for(payload, manager_user, finish=1736294400))
    assert resp.status_code == 201
    assert WorkVolume.objects.count() == 2


def test_tsdb_failure_rolls_back(api_client, manager_user, payload, fake_tsdb, failing_tsdb):
    # failing_tsdb is applied after fake_tsdb, so it wins
    resp = post(api_client, manager_user, body_for(payload, manager_user))
    assert_error(resp, 503, 904)
    assert WorkVolume.objects.count() == 0


def test_tsdb_failure_keeps_existing(api_client, manager_user, payload, fake_tsdb, monkeypatch):
    post(api_client, manager_user, body_for(payload, manager_user))
    from plan import services
    from tests.conftest import FailingRepo

    monkeypatch.setattr(services, "get_work_volume_record_repository", lambda: FailingRepo())
    resp = post(api_client, manager_user, body_for(payload, manager_user, weight=9999))
    assert_error(resp, 503, 904)
    assert WorkVolume.objects.get().weight == 1500


def test_token_auth(api_client, manager_user, payload, fake_tsdb):
    token = Token.objects.create(user=manager_user)
    resp = api_client.post(
        URL,
        data=json.dumps(body_for(payload, manager_user)),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {token.key}",
    )
    assert resp.status_code == 201


def test_extra_field(api_client, manager_user, payload, fake_tsdb):
    resp = post(api_client, manager_user, body_for(payload, manager_user, extra="x"))
    assert resp.status_code == 201


def test_deeply_nested_json_is_json_error(api_client, manager_user):
    api_client.force_authenticate(manager_user)
    body = "[" * 100000 + "]" * 100000
    resp = api_client.post(URL, data=body, content_type="application/json")
    assert_error(resp, 400, 901)


def test_unexpected_exception_is_json_500(api_client, manager_user, monkeypatch):
    from plan import services

    def boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(services, "save_work_volume", boom)
    api_client.raise_request_exception = False
    resp = post(
        api_client,
        manager_user,
        {
            "factory": 1,
            "start": 0,
            "finish": 0,
            "weight": 1,
            "author": manager_user.pk,
        },
    )
    assert_error(resp, 500, 999)


def test_unauthenticated_beats_not_acceptable(api_client):
    resp = api_client.post(
        URL, data="{}", content_type="application/json", HTTP_ACCEPT="application/xml"
    )
    assert_error(resp, 401, 900)


def test_not_acceptable_when_authenticated(api_client, manager_user):
    api_client.force_authenticate(manager_user)
    resp = api_client.post(
        URL, data="{}", content_type="application/json", HTTP_ACCEPT="application/xml"
    )
    assert_error(resp, 406, 907)


def test_csrf_failure_is_not_902(db):
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient

    client = APIClient(enforce_csrf_checks=True)
    get_user_model().objects.create_user(username="sess", password="pw12345678")
    client.login(username="sess", password="pw12345678")
    resp = client.post(URL, data={}, format="json")
    assert_error(resp, 403, 908)


def test_slash_optional(api_client, manager_user):
    api_client.force_authenticate(manager_user)
    resp = api_client.post("/work-volume-list", data={}, format="json")
    assert_error(resp, 406, 279)


def test_messages_are_english(api_client, payload, manager_user):
    resp = api_client.post(URL, data={}, format="json")
    assert resp.json()["message"] == "Authentication credentials were not provided."
    api_client.force_authenticate(manager_user)
    resp = api_client.get(URL)
    assert "not allowed" in resp.json()["message"]
    resp = post(api_client, manager_user, payload(author=manager_user.pk, weight=2147483648))
    assert "less than or equal" in str(resp.json()["details"]["weight"])
