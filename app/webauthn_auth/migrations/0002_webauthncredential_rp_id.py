"""Guarda el RP ID con el que se creó cada passkey.

**No se rellenan las filas existentes, y es deliberado.** Se quedan con `""`, que
no coincide con ningún `WEBAUTHN_RP_ID`, así que quedan marcadas como muertas —
que es justo lo que son: se crearon contra `atlas.atharix.com` y el RP vigente
pasó a ser `atharix.com`, de modo que el autenticador ya no las ofrece.

La tentación es rellenarlas con `settings.WEBAUTHN_RP_ID`, y sería el error
exacto que este cambio viene a corregir: las daría por vivas, el listado seguiría
diciendo "ya tienes passkey", la app no ofrecería registrar otra, y el usuario
seguiría sin poder entrar.

Tampoco se escribe `atlas.atharix.com` a mano: dejarlas en blanco produce el
mismo resultado sin clavar un dominio en una migración. Efecto colateral asumido:
en desarrollo (RP `localhost`) las passkeys locales también dejan de contar y hay
que registrarlas de nuevo — coste trivial.

Las filas NO se borran: quedan como rastro de auditoría, simplemente dejan de
contar. Se pueden purgar más adelante si molestan.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("webauthn_auth", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="webauthncredential",
            name="rp_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255),
        ),
    ]
