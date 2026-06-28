from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_branded_email(
    *,
    subject,
    recipients,
    text_body,
    title,
    intro,
    greeting='Halo,',
    eyebrow='Notifikasi LabHub',
    details=None,
    action_url=None,
    action_label=None,
    highlight=None,
    note=None,
    fail_silently=False,
):
    recipients = [email for email in recipients if email]
    if not recipients:
        return 0

    html_body = render_to_string('emails/labhub_notification.html', {
        'subject': subject,
        'title': title,
        'intro': intro,
        'greeting': greeting,
        'eyebrow': eyebrow,
        'details': details or [],
        'action_url': action_url,
        'action_label': action_label,
        'highlight': highlight,
        'note': note,
        'portal_url': settings.PUBLIC_ACCESS_BASE_URL,
    })
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        to=recipients,
    )
    email.attach_alternative(html_body, 'text/html')
    return email.send(fail_silently=fail_silently)
