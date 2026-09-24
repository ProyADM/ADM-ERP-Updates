# modules/shared/correo_outlook.py
# ============================================================
# ENVIO DEL INFORME POR EL OUTLOOK DEL USUARIO - SIDESYS ERP
# ============================================================
# Brief 23/09/2026 ("Enviar el informe por correo desde Outlook") y brief
# 24/09/2026 ("Argentina por sociedad, nombre del archivo y envio directo"),
# que revierte la decision de aquel: el correo YA NO queda como borrador abierto.
#
# Que hace y que NO hace:
#   - ARMA el correo con destinatarios, asunto, cuerpo y el adjunto, y lo ENVIA
#     (`Send()`) por el Outlook de la PC donde corre la aplicacion. Usa el
#     remitente del usuario de esa sesion de Windows: no hay contrasenas ni SMTP.
#   - NO espera confirmacion de entrega: `Send()` es asincrono (Outlook encola y
#     el servidor de correo entrega despues). Lo que devuelve esta funcion es que
#     Outlook ACEPTO el envio, no que el destinatario lo haya recibido.
#   - NO hay paso de revision propio: el dialogo del frontend (destinatarios,
#     asunto y mensaje editables) ES la revision. En algunas configuraciones de
#     Outlook puede aparecer una confirmacion de seguridad al enviar.
#
# Dos decisiones que se ven en el codigo:
#   1. El import de `win32com.client` es PEREZOSO (adentro de la funcion): la app
#      tiene que poder arrancar en una PC sin pywin32. Si el import falla, se
#      devuelve `(False, ...)` con un mensaje claro.
#   2. `crear_app` es INYECTABLE: las pruebas pasan un doble y ejercitan todo el
#      armado y el envio sin abrir Outlook (y sin mandar ningun correo real).
#      En produccion no se pasa y la fabrica por defecto es `win32com.client.Dispatch`.
#
# El modulo es PURO stdlib: no importa Flask, config, database ni la app, para
# poder testearlo solo. `enviar_informe` NO propaga excepciones: siempre
# devuelve `(ok, detalle)`.
# ============================================================

import logging
import os

logger = logging.getLogger(__name__)

# Outlook: `CreateItem(0)` = MailItem (el 0 es `olMailItem` de la libreria de
# objetos de Outlook; no hay que importar la libreria para conocerlo).
OL_MAIL_ITEM = 0

# Prohibido en los encabezados: un CR/LF abre un encabezado nuevo (inyeccion).
_SALTOS = ('\r', '\n')


def _fabrica_por_defecto():
    """Fabrica real: un `Outlook.Application` por COM.

    El import esta ACA adentro a proposito (ver el encabezado del modulo): en una
    PC sin pywin32 esto levanta `ImportError` y `enviar_informe` lo convierte en
    un mensaje claro en vez de tumbar la aplicacion."""
    import win32com.client  # noqa: F401  (import perezoso, requerido por el brief)
    return win32com.client.Dispatch('Outlook.Application')


def _detalle_de_error(error):
    """Mensaje de una excepcion, sin quedarse vacio y sin romper si no tiene texto."""
    texto = str(error).strip()
    if texto:
        return texto
    return error.__class__.__name__


def enviar_informe(ruta_adjunto, para, asunto, cuerpo, crear_app=None):
    """ENVIA un correo por Outlook con el adjunto. Devuelve `(ok, detalle)`.

    Devuelve `(ok: bool, detalle: str)` y NUNCA propaga excepciones: el endpoint
    que la llama tiene que poder responderle al usuario un mensaje claro.
    `ok` significa que Outlook acepto el envio (`Send()` no fallo); la entrega la
    hace el servidor de correo, mas tarde.

    `crear_app` es la fabrica del objeto COM (0 argumentos). Se inyecta en las
    pruebas para no abrir Outlook; en produccion se usa la de COM.
    """
    # --- Validaciones de entrada: no tocan Outlook --------------------------
    ruta = '' if ruta_adjunto is None else str(ruta_adjunto)
    if not ruta:
        return False, 'No se indicó el archivo a adjuntar.'
    if not os.path.isfile(ruta):
        return False, f'No se encontró el archivo a adjuntar: {ruta}'

    destinatarios = '' if para is None else str(para).strip()
    if not destinatarios:
        return False, 'No se indicó ningún destinatario.'

    asunto = '' if asunto is None else str(asunto)
    cuerpo = '' if cuerpo is None else str(cuerpo)
    # Los encabezados de un correo no admiten saltos de linea: en vez de fallar,
    # se reemplazan por un espacio (el asunto sigue siendo el que el usuario
    # escribio, en una sola linea).
    for salto in _SALTOS:
        asunto = asunto.replace(salto, ' ')
    asunto = ' '.join(asunto.split())
    cuerpo = '\n'.join(linea.rstrip() for linea in
                       cuerpo.replace('\r\n', '\n').replace('\r', '\n').split('\n')).strip()

    fabrica = crear_app or _fabrica_por_defecto

    # --- Armado y envio -----------------------------------------------------
    try:
        app = fabrica()
    except ImportError:
        mensaje = ('No está disponible pywin32 en esta PC: no se puede enviar el '
                   'informe por Outlook.')
        logger.warning('correo_outlook: %s', mensaje)
        return False, mensaje
    except Exception as e:
        mensaje = (f'No se pudo iniciar Outlook en esta PC: {_detalle_de_error(e)}. '
                   'Verificá que Outlook esté instalado.')
        logger.warning('correo_outlook: %s', mensaje)
        return False, mensaje

    try:
        correo = app.CreateItem(OL_MAIL_ITEM)
        correo.To = destinatarios
        correo.Subject = asunto
        correo.Body = cuerpo
        adjuntos = correo.Attachments
        adjuntos.Add(ruta)
        # `Send()` = el correo SALE por el Outlook de esta PC (brief 24/09/2026).
        # Outlook ENCOLA: la confirmacion de entrega es del servidor de correo.
        correo.Send()
    except Exception as e:
        mensaje = (f'No se pudo enviar el correo por Outlook: {_detalle_de_error(e)}')
        logger.error('correo_outlook: %s (adjunto %s)', mensaje, ruta)
        return False, mensaje

    logger.info('correo_outlook: informe enviado por Outlook (adjunto %s)', ruta)
    return True, 'Se envió el informe por correo.'
