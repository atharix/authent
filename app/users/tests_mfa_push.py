"""Aprobación del login desde la app: el teléfono como segundo factor.

La prueba que más importa aquí no es la del camino feliz, sino la de que nadie
se quede fuera: sin app enrolada el login tiene que seguir comportándose
exactamente como hoy.
"""

from datetime import timedelta
from unittest import mock

from apps.models import APIKey, Application
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from users.models import User
from users.models.mfa import EmailOtp, LoginApproval, PushApprover, TrustedDevice

LOGIN_URL = "/api/auth/login/"
STATUS_URL = "/api/auth/mfa/approval/status/"
APPROVALS_URL = "/api/auth/mfa/approvals/"
APPROVERS_URL = "/api/auth/mfa/approvers/"
FALLBACK_URL = "/api/auth/mfa/approval/fallback/"
PASSWORD = "Sup3rSecreta!"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PUSH_APPROVAL_ENABLED=True,
)
class PushApprovalLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="lmendoza@projects.ec",
            password=PASSWORD,
            first_name="Luis",
            last_name="Mendoza",
        )
        self.app = Application.objects.create(
            name="Atlas", code="atlas", enforce_mfa=True
        )
        self.key = APIKey.objects.create(application=self.app, name="test")
        self.client = APIClient()

    # ── Helpers ─────────────────────────────────────────────────────────────
    def enrol(self, user=None, delivery_ref="expo-token-1"):
        return PushApprover.objects.create(
            user=user or self.user,
            application_code="atlas",
            delivery_ref=delivery_ref,
            device_label="iPhone de Luis",
            platform="ios",
        )

    def login(self, **extra):
        return self.client.post(
            LOGIN_URL,
            {"email": self.user.email, "password": PASSWORD, **extra},
            format="json",
            HTTP_X_API_KEY=self.key.key,
        )

    def poll(self, mfa_token, **extra):
        return self.client.post(
            STATUS_URL,
            {"mfa_token": mfa_token, **extra},
            format="json",
            HTTP_X_API_KEY=self.key.key,
        )

    def fallback(self, mfa_token):
        return self.client.post(
            FALLBACK_URL,
            {"mfa_token": mfa_token},
            format="json",
            HTTP_X_API_KEY=self.key.key,
        )

    def current_code(self):
        """Reproduce el código del correo leyendo el cuerpo del mensaje."""
        digits = [w for w in mail.outbox[-1].body.split() if w.isdigit() and len(w) == 6]
        return digits[0]

    def as_app(self, user=None):
        """Cliente con sesión iniciada, como la app hablando por el proxy."""
        client = APIClient()
        client.credentials(HTTP_X_API_KEY=self.key.key)
        client.force_authenticate(user=user or self.user)
        return client

    # ── Sin app detrás: nada cambia ─────────────────────────────────────────
    def test_sin_aprobador_enrolado_el_login_manda_codigo_por_correo(self):
        """Quien nunca ha instalado la app entra como siempre."""
        body = self.login().json()

        self.assertTrue(body["mfa_required"])
        self.assertEqual(body["mfa_method"], "email")
        self.assertNotIn("expected_number", body)
        self.assertFalse(LoginApproval.objects.exists())

    @override_settings(PUSH_APPROVAL_ENABLED=False)
    def test_con_la_bandera_apagada_el_aprobador_no_cuenta(self):
        """El interruptor de despliegue manda por encima del enrolamiento."""
        self.enrol()

        body = self.login().json()

        self.assertEqual(body["mfa_method"], "email")
        self.assertFalse(LoginApproval.objects.exists())

    def test_revocar_el_aprobador_devuelve_el_login_al_correo(self):
        approver = self.enrol()
        approver.revoke()

        self.assertEqual(self.login().json()["mfa_method"], "email")

    # ── Desafío ─────────────────────────────────────────────────────────────
    def test_con_aprobador_el_login_abre_una_solicitud_y_no_da_tokens(self):
        self.enrol()

        body = self.login().json()

        self.assertEqual(body["mfa_method"], "push")
        self.assertNotIn("access", body)
        self.assertNotIn("refresh", body)
        approval = LoginApproval.objects.get()
        self.assertEqual(body["expected_number"], approval.expected_number)
        self.assertEqual(body["delivery"]["approval_id"], str(approval.id))
        self.assertEqual(body["delivery"]["approver_ref"], "expo-token-1")

    def test_el_desafio_no_revela_los_tres_numeros(self):
        """Los candidatos solo salen por la sesión de la app, nunca al navegador."""
        self.enrol()

        body = self.login().json()

        self.assertNotIn("numbers", body)

    def test_una_solicitud_nueva_tumba_la_anterior(self):
        self.enrol()
        first = self.login().json()
        self.login()

        self.assertEqual(self.poll(first["mfa_token"]).json()["status"], "denied")

    def test_el_equipo_de_confianza_se_salta_la_aprobacion(self):
        self.enrol()
        _, raw = TrustedDevice.issue(self.user, application_code="atlas")

        body = self.login(device_token=raw).json()

        self.assertIn("access", body)
        self.assertFalse(LoginApproval.objects.exists())

    # ── Lo que ve la app ────────────────────────────────────────────────────
    def test_la_app_ve_la_solicitud_pendiente_con_sus_tres_numeros(self):
        self.enrol()
        self.login()

        body = self.as_app().get(APPROVALS_URL).json()
        item = body["results"][0] if isinstance(body, dict) else body[0]

        self.assertEqual(len(item["numbers"]), 3)
        self.assertEqual(len(set(item["numbers"])), 3)
        approval = LoginApproval.objects.get()
        self.assertIn(approval.expected_number, item["numbers"])

    def test_la_app_no_ve_solicitudes_de_otra_cuenta(self):
        otra = User.objects.create_user(
            email="ajena@projects.ec", password=PASSWORD,
            first_name="A", last_name="B",
        )
        self.enrol()
        self.login()

        body = self.as_app(user=otra).get(APPROVALS_URL).json()
        results = body["results"] if isinstance(body, dict) else body

        self.assertEqual(results, [])

    # ── Aprobar ─────────────────────────────────────────────────────────────
    def test_el_numero_correcto_aprueba_y_el_sondeo_entrega_los_tokens(self):
        self.enrol()
        challenge = self.login().json()
        approval = LoginApproval.objects.get()

        approved = self.as_app().post(
            f"{APPROVALS_URL}{approval.id}/approve/",
            {"number": approval.expected_number},
            format="json",
        )
        self.assertEqual(approved.status_code, 200)

        body = self.poll(challenge["mfa_token"]).json()
        self.assertEqual(body["status"], "approved")
        self.assertIn("access", body)
        self.assertIn("refresh", body)

    def test_el_sondeo_solo_entrega_los_tokens_una_vez(self):
        self.enrol()
        challenge = self.login().json()
        approval = LoginApproval.objects.get()
        self.as_app().post(
            f"{APPROVALS_URL}{approval.id}/approve/",
            {"number": approval.expected_number},
            format="json",
        )
        self.poll(challenge["mfa_token"])

        self.assertEqual(self.poll(challenge["mfa_token"]).status_code, 401)

    def test_recordar_el_equipo_emite_el_sello_de_confianza(self):
        self.enrol()
        challenge = self.login().json()
        approval = LoginApproval.objects.get()
        self.as_app().post(
            f"{APPROVALS_URL}{approval.id}/approve/",
            {"number": approval.expected_number},
            format="json",
        )

        body = self.poll(
            challenge["mfa_token"], remember_device=True, device_name="Chrome · Windows"
        ).json()

        self.assertIn("device_token", body)
        self.assertEqual(body["device_trusted_days"], TrustedDevice.TTL_DAYS)

    # ── Rechazar ────────────────────────────────────────────────────────────
    def test_el_numero_equivocado_tumba_el_intento_sin_segunda_oportunidad(self):
        self.enrol()
        challenge = self.login().json()
        approval = LoginApproval.objects.get()
        wrong = next(n for n in approval.numbers if n != approval.expected_number)

        response = self.as_app().post(
            f"{APPROVALS_URL}{approval.id}/approve/", {"number": wrong}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "approval_number_mismatch")
        self.assertEqual(self.poll(challenge["mfa_token"]).json()["status"], "denied")

    def test_rechazar_desde_la_app_cierra_el_intento(self):
        self.enrol()
        challenge = self.login().json()
        approval = LoginApproval.objects.get()

        self.as_app().post(f"{APPROVALS_URL}{approval.id}/deny/", format="json")

        self.assertEqual(self.poll(challenge["mfa_token"]).json()["status"], "denied")

    def test_nadie_aprueba_la_solicitud_de_otro(self):
        intruso = User.objects.create_user(
            email="intruso@projects.ec", password=PASSWORD,
            first_name="I", last_name="N",
        )
        self.enrol()
        self.login()
        approval = LoginApproval.objects.get()

        response = self.as_app(user=intruso).post(
            f"{APPROVALS_URL}{approval.id}/approve/",
            {"number": approval.expected_number},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        approval.refresh_from_db()
        self.assertEqual(approval.status, LoginApproval.PENDING)

    # ── Caducidad ───────────────────────────────────────────────────────────
    def test_la_solicitud_caduca_a_los_dos_minutos(self):
        self.enrol()
        challenge = self.login().json()
        approval = LoginApproval.objects.get()
        approval.expires_at = timezone.now() - timedelta(seconds=1)
        approval.save(update_fields=["expires_at"])

        self.assertEqual(self.poll(challenge["mfa_token"]).json()["status"], "expired")

    def test_una_solicitud_caducada_ya_no_se_puede_aprobar(self):
        self.enrol()
        self.login()
        approval = LoginApproval.objects.get()
        approval.expires_at = timezone.now() - timedelta(seconds=1)
        approval.save(update_fields=["expires_at"])

        response = self.as_app().post(
            f"{APPROVALS_URL}{approval.id}/approve/",
            {"number": approval.expected_number},
            format="json",
        )

        self.assertEqual(response.status_code, 409)

    # ── Enrolamiento ────────────────────────────────────────────────────────
    def test_la_app_se_enrola_desde_su_propia_sesion(self):
        response = self.as_app().post(
            APPROVERS_URL,
            {
                "delivery_ref": "expo-token-9",
                "device_label": "iPhone de Luis",
                "platform": "ios",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            PushApprover.objects.filter(
                user=self.user, delivery_ref="expo-token-9", revoked_at__isnull=True
            ).exists()
        )

    def test_reenrolar_el_mismo_aparato_no_duplica(self):
        client = self.as_app()
        payload = {"delivery_ref": "expo-token-9", "device_label": "iPhone"}
        client.post(APPROVERS_URL, payload, format="json")
        client.post(APPROVERS_URL, {**payload, "device_label": "iPhone 15"}, format="json")

        approvers = PushApprover.objects.filter(user=self.user, revoked_at__isnull=True)
        self.assertEqual(approvers.count(), 1)
        self.assertEqual(approvers.get().device_label, "iPhone 15")

    def test_dar_de_baja_el_aprobador_lo_revoca(self):
        approver = self.enrol()

        response = self.as_app().delete(f"{APPROVERS_URL}{approver.id}/")

        self.assertEqual(response.status_code, 204)
        approver.refresh_from_db()
        self.assertIsNotNone(approver.revoked_at)

    # ── Salida por correo cuando el teléfono ya no está ─────────────────────
    def test_sin_el_telefono_el_desafio_se_cambia_por_un_codigo_al_correo(self):
        """Perder el móvil no puede ser perder la cuenta."""
        self.enrol()
        challenge = self.login().json()

        body = self.fallback(challenge["mfa_token"]).json()

        self.assertEqual(body["mfa_method"], "email")
        self.assertNotIn("access", body)
        self.assertEqual(EmailOtp.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_el_codigo_del_correo_entrega_los_tokens(self):
        self.enrol()
        challenge = self.login().json()
        fallback = self.fallback(challenge["mfa_token"]).json()
        otp = EmailOtp.objects.get(user=self.user)
        code = self.current_code()

        response = self.client.post(
            "/api/auth/mfa/verify/",
            {"mfa_token": fallback["mfa_token"], "code": code},
            format="json",
            HTTP_X_API_KEY=self.key.key,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        otp.refresh_from_db()
        self.assertEqual(otp.status, EmailOtp.USED)

    def test_abandonar_el_desafio_mata_la_solicitud_de_la_app(self):
        """Un push que llega tarde no puede aprobar lo que ya se abandonó."""
        self.enrol()
        challenge = self.login().json()

        self.fallback(challenge["mfa_token"])

        approval = LoginApproval.objects.get()
        self.assertEqual(approval.status, LoginApproval.DENIED)
        self.assertEqual(self.poll(challenge["mfa_token"]).json()["status"], "denied")

    def test_no_se_puede_abandonar_dos_veces_el_mismo_desafio(self):
        self.enrol()
        challenge = self.login().json()
        self.fallback(challenge["mfa_token"])

        response = self.fallback(challenge["mfa_token"])

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["code"], "mfa_restart")

    def test_una_solicitud_caducada_no_da_codigo_por_correo(self):
        self.enrol()
        challenge = self.login().json()
        approval = LoginApproval.objects.get()
        approval.expires_at = timezone.now() - timedelta(seconds=1)
        approval.save(update_fields=["expires_at"])

        response = self.fallback(challenge["mfa_token"])

        self.assertEqual(response.status_code, 401)
        self.assertEqual(EmailOtp.objects.count(), 0)

    def test_un_token_inventado_no_manda_ningun_correo(self):
        response = self.fallback("no-es-un-token")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(len(mail.outbox), 0)

    def test_si_el_correo_falla_la_solicitud_de_la_app_sigue_viva(self):
        """Sin relevo no se quema el camino que aún funcionaba."""
        self.enrol()
        challenge = self.login().json()

        with mock.patch(
            "users.utils.mfa.send_otp_email", return_value=False
        ):
            response = self.fallback(challenge["mfa_token"])

        self.assertEqual(response.status_code, 503)
        self.assertEqual(LoginApproval.objects.get().status, LoginApproval.PENDING)
