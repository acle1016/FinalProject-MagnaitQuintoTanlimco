from django.db import models


class Employee(models.Model):
    """
    Represents a Shemu employee.
    overtime_pay and allowance are nullable — they're optional at creation.
    """
    name = models.CharField(max_length=200)
    id_number = models.CharField(max_length=50, unique=True)
    rate = models.FloatField()
    overtime_pay = models.FloatField(null=True, blank=True, default=0)
    allowance = models.FloatField(null=True, blank=True, default=0)

    # ── Getter methods as specified ──────────────────────────────────────────
    def getName(self):
        return self.name

    def getID(self):
        return self.id_number

    def getRate(self):
        return self.rate

    def getOvertime(self):
        return self.overtime_pay or 0

    def resetOvertime(self):
        """Zeroes out overtime after a payslip is generated."""
        self.overtime_pay = 0
        self.save()

    def getAllowance(self):
        return self.allowance or 0

    def __str__(self):
        return f"pk: {self.id_number}, rate: {self.rate}"


class Payslip(models.Model):
    """
    A single pay-cycle record tied to an Employee via their id_number FK.
    All fields required; 0 is used for absent values.
    """
    # FK references the Employee model (id_number field)
    id_number = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        to_field='id_number',
        db_column='employee_id_number'
    )
    month = models.CharField(max_length=20)
    date_range = models.CharField(max_length=50)
    year = models.CharField(max_length=10)
    pay_cycle = models.IntegerField()
    rate = models.FloatField()
    earnings_allowance = models.FloatField()
    deductions_tax = models.FloatField()
    deductions_health = models.FloatField()
    pag_ibig = models.FloatField()
    sss = models.FloatField()
    overtime = models.FloatField()
    total_pay = models.FloatField()

    # ── Getter methods ────────────────────────────────────────────────────────
    def getIDNumber(self):
        return self.id_number.id_number

    def getMonth(self):
        return self.month

    def getDate_range(self):
        return self.date_range

    def getYear(self):
        return self.year

    def getPay_cycle(self):
        return self.pay_cycle

    def getRate(self):
        return self.rate

    def getCycleRate(self):
        """Half the monthly rate — the base for each pay cycle."""
        return self.rate / 2

    def getEarnings_allowance(self):
        return self.earnings_allowance

    def getDeductions_tax(self):
        return self.deductions_tax

    def getDeductions_health(self):
        return self.deductions_health

    def getPag_ibig(self):
        return self.pag_ibig

    def getSSS(self):
        return self.sss

    def getOvertime(self):
        return self.overtime

    def getTotal_pay(self):
        return self.total_pay

    def __str__(self):
        return (
            f"pk: {self.pk}, Employee: {self.id_number.id_number}, "
            f"Period: {self.month} {self.date_range}, {self.year}, "
            f"Cycle: {self.pay_cycle}, Total Pay: {self.total_pay}"
        )

    @property
    def gross_pay(self):
        """Cycle rate + allowance + overtime (before deductions)."""
        return (self.rate / 2) + self.earnings_allowance + self.overtime

    @property
    def total_deductions(self):
        """Sum of all applicable deductions for the cycle."""
        if self.pay_cycle == 1:
            return self.deductions_tax + self.pag_ibig
        else:
            return self.deductions_tax + self.deductions_health + self.sss
