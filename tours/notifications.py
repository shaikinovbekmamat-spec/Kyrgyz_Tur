import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def notify_new_comment(comment, url):
    """Ошибка SMTP не должна мешать сохранению комментария."""
    if not settings.COMMENT_NOTIFICATION_EMAIL:
        return
    try:
        send_mail(
            f'Kyrgyz Tur: новый комментарий #{comment.pk}',
            f'Тур: {comment.tour.name}\nАвтор: {comment.user.username}\n'
            f'Тема: {comment.subject}\n\n{comment.text}\n\n{url}',
            settings.DEFAULT_FROM_EMAIL,
            [settings.COMMENT_NOTIFICATION_EMAIL],
        )
    except (SMTPException, OSError, ValueError):
        logger.exception('Не удалось отправить уведомление о комментарии %s', comment.pk)
