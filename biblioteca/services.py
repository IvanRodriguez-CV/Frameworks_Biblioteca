from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from biblioteca.models import BookCopy, Loan


class Conflict(APIException):
    status_code = 409
    default_detail = "La operación entra en conflicto con el estado actual del recurso."
    default_code = "conflict"


@transaction.atomic
def create_loan(*, user, copy_id, due_date=None):
    due_date = due_date or (timezone.localdate() + timedelta(days=14))
    if due_date < timezone.localdate():
        raise ValidationError({"due_date": "La fecha de devolución no puede estar en el pasado."})

    try:
        copy = BookCopy.objects.select_related("book").get(pk=copy_id)
    except BookCopy.DoesNotExist as exc:
        raise ValidationError({"copy": "El ejemplar solicitado no existe."}) from exc

    updated = BookCopy.objects.filter(
        pk=copy.pk,
        status=BookCopy.Status.AVAILABLE,
    ).update(status=BookCopy.Status.LOANED)
    if updated != 1:
        raise Conflict("El ejemplar no está disponible para préstamo.")

    return Loan.objects.create(user=user, copy=copy, due_date=due_date)


@transaction.atomic
def return_loan(*, loan_id):
    now = timezone.now()
    updated = Loan.objects.filter(
        pk=loan_id,
        status=Loan.Status.ACTIVE,
    ).update(status=Loan.Status.RETURNED, returned_at=now)
    if updated != 1:
        if not Loan.objects.filter(pk=loan_id).exists():
            raise ValidationError({"loan": "El préstamo solicitado no existe."})
        raise Conflict("El préstamo ya fue devuelto.")

    loan = Loan.objects.select_related("copy").get(pk=loan_id)
    BookCopy.objects.filter(pk=loan.copy_id).update(status=BookCopy.Status.AVAILABLE)
    loan.refresh_from_db()
    return loan
