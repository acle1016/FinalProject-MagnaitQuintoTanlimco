from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Employee, Payslip

# ── Constants ────────────────────────────────────────────────────────────────
TAX_RATE = 0.20
PAGIBIG_FLAT = 100.0
PHILHEALTH_RATE = 0.04
SSS_RATE = 0.045

MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]

# Date ranges per cycle
CYCLE_DATE_RANGES = {
    '1': '1-15',
    '2': '16-30',
}


# ════════════════════════════════════════════════════════
# EMPLOYEE VIEWS
# ════════════════════════════════════════════════════════

def worker_roster(request):
    """Home page – shows all employees in a table."""
    all_workers = Employee.objects.all().order_by('name')
    return render(request, 'payroll_app/employees.html', {
        'workers': all_workers,
    })


def worker_create(request):
    """Form to create a new employee."""
    if request.method == 'POST':
        worker_name = request.POST.get('name', '').strip()
        worker_id = request.POST.get('id_number', '').strip()
        worker_rate = request.POST.get('rate', '').strip()
        worker_allowance = request.POST.get('allowance', '').strip()

        # Basic validation
        if not worker_name or not worker_id or not worker_rate:
            messages.error(request, 'Name, ID Number, and Rate are required.')
            return render(request, 'payroll_app/employee_form.html', {
                'form_mode': 'create',
                'form_data': request.POST,
            })

        # Unique ID check
        if Employee.objects.filter(id_number=worker_id).exists():
            messages.error(request, f'An employee with ID "{worker_id}" already exists.')
            return render(request, 'payroll_app/employee_form.html', {
                'form_mode': 'create',
                'form_data': request.POST,
            })

        Employee.objects.create(
            name=worker_name,
            id_number=worker_id,
            rate=float(worker_rate),
            allowance=float(worker_allowance) if worker_allowance else None,
            overtime_pay=0,
        )
        messages.success(request, f'Employee "{worker_name}" added successfully!')
        return redirect('worker-roster')

    return render(request, 'payroll_app/employee_form.html', {'form_mode': 'create'})


def worker_edit(request, worker_pk):
    """Form to update an existing employee's details."""
    target_worker = get_object_or_404(Employee, pk=worker_pk)

    if request.method == 'POST':
        worker_name = request.POST.get('name', '').strip()
        worker_id = request.POST.get('id_number', '').strip()
        worker_rate = request.POST.get('rate', '').strip()
        worker_allowance = request.POST.get('allowance', '').strip()

        if not worker_name or not worker_id or not worker_rate:
            messages.error(request, 'Name, ID Number, and Rate are required.')
            return render(request, 'payroll_app/employee_form.html', {
                'form_mode': 'edit',
                'worker': target_worker,
            })

        # Check uniqueness — but exclude self
        if Employee.objects.filter(id_number=worker_id).exclude(pk=worker_pk).exists():
            messages.error(request, f'Another employee already has ID "{worker_id}".')
            return render(request, 'payroll_app/employee_form.html', {
                'form_mode': 'edit',
                'worker': target_worker,
            })

        target_worker.name = worker_name
        target_worker.id_number = worker_id
        target_worker.rate = float(worker_rate)
        target_worker.allowance = float(worker_allowance) if worker_allowance else None
        target_worker.save()

        messages.success(request, f'Employee "{worker_name}" updated!')
        return redirect('worker-roster')

    return render(request, 'payroll_app/employee_form.html', {
        'form_mode': 'edit',
        'worker': target_worker,
    })


def worker_remove(request, worker_pk):
    """Delete an employee record."""
    target_worker = get_object_or_404(Employee, pk=worker_pk)
    removed_name = target_worker.name
    target_worker.delete()
    messages.success(request, f'Employee "{removed_name}" has been removed.')
    return redirect('worker-roster')


def worker_overtime(request, worker_pk):
    """Add overtime hours to an employee and compute overtime pay."""
    target_worker = get_object_or_404(Employee, pk=worker_pk)

    if request.method == 'POST':
        ot_hours_raw = request.POST.get('ot_hours', '').strip()
        try:
            ot_hours = float(ot_hours_raw)
            if ot_hours <= 0:
                raise ValueError('Hours must be positive')
        except ValueError:
            messages.error(request, 'Please enter a valid positive number of overtime hours.')
            return redirect('worker-roster')

        # Overtime = (Rate / 160) × 1.5 × OT Hours
        computed_ot = (target_worker.rate / 160) * 1.5 * ot_hours
        current_ot = target_worker.overtime_pay or 0
        target_worker.overtime_pay = current_ot + computed_ot
        target_worker.save()

        messages.success(
            request,
            f'Added PHP {computed_ot:.2f} overtime to {target_worker.name}.'
        )

    return redirect('worker-roster')


# ════════════════════════════════════════════════════════
# PAYSLIP VIEWS
# ════════════════════════════════════════════════════════

def slip_ledger(request):
    """
    Main payslips page — shows creation form and payslips summary table.
    Handles payroll generation for one or all employees.
    """
    all_workers = Employee.objects.all().order_by('name')
    all_slips = Payslip.objects.all().select_related('id_number').order_by('-pk')

    form_errors = []

    if request.method == 'POST':
        payroll_target = request.POST.get('payroll_for', '').strip()
        chosen_month = request.POST.get('month', '').strip()
        chosen_year = request.POST.get('year', '').strip()
        chosen_cycle = request.POST.get('cycle', '').strip()

        # Validate inputs
        if not payroll_target or not chosen_month or not chosen_year or not chosen_cycle:
            form_errors.append('All fields in the Payroll Creation form are required.')
        else:
            # Determine which employees to process
            if payroll_target == 'all':
                workers_to_pay = list(all_workers)
            else:
                workers_to_pay = list(Employee.objects.filter(id_number=payroll_target))

            if not workers_to_pay:
                form_errors.append('No employees found for the selected option.')
            else:
                cycle_num = int(chosen_cycle)
                date_range_str = CYCLE_DATE_RANGES.get(chosen_cycle, '1-15')
                created_count = 0
                duplicate_ids = []

                for worker in workers_to_pay:
                    # Duplicate check: same employee + month + year + cycle
                    already_exists = Payslip.objects.filter(
                        id_number=worker,
                        month=chosen_month,
                        year=chosen_year,
                        pay_cycle=cycle_num,
                    ).exists()

                    if already_exists:
                        duplicate_ids.append(worker.id_number)
                        continue

                    # ── Payslip calculations ──────────────────────────────
                    half_rate = worker.rate / 2
                    allowance_val = worker.getAllowance()
                    overtime_val = worker.getOvertime()

                    if cycle_num == 1:
                        # Cycle 1: Pag-ibig deduction
                        pagibig_val = PAGIBIG_FLAT
                        philhealth_val = 0.0
                        sss_val = 0.0

                        tax_val = (half_rate + allowance_val + overtime_val - pagibig_val) * TAX_RATE
                        gross = half_rate + allowance_val + overtime_val - pagibig_val
                        net_pay = gross - tax_val

                    else:
                        # Cycle 2: Philhealth + SSS deductions
                        pagibig_val = 0.0
                        philhealth_val = worker.rate * PHILHEALTH_RATE
                        sss_val = worker.rate * SSS_RATE

                        tax_val = (half_rate + allowance_val + overtime_val - philhealth_val - sss_val) * TAX_RATE
                        gross = half_rate + allowance_val + overtime_val - philhealth_val - sss_val
                        net_pay = gross - tax_val

                    Payslip.objects.create(
                        id_number=worker,
                        month=chosen_month,
                        date_range=f'{date_range_str}, {chosen_year}',
                        year=chosen_year,
                        pay_cycle=cycle_num,
                        rate=worker.rate,
                        earnings_allowance=allowance_val,
                        deductions_tax=round(tax_val, 2),
                        deductions_health=round(philhealth_val, 2),
                        pag_ibig=round(pagibig_val, 2),
                        sss=round(sss_val, 2),
                        overtime=round(overtime_val, 2),
                        total_pay=round(net_pay, 2),
                    )

                    # Reset overtime per spec
                    worker.resetOvertime()
                    created_count += 1

                if duplicate_ids:
                    form_errors.append(
                        f'Payslip already exists for: {", ".join(duplicate_ids)}. '
                        f'Skipped {len(duplicate_ids)} duplicate(s).'
                    )
                if created_count > 0:
                    messages.success(
                        request,
                        f'Successfully generated {created_count} payslip(s) for {chosen_month} {chosen_year}, Cycle {chosen_cycle}.'
                    )

                # Refresh slip list after creation
                all_slips = Payslip.objects.all().select_related('id_number').order_by('-pk')

    return render(request, 'payroll_app/payslips.html', {
        'workers': all_workers,
        'all_slips': all_slips,
        'months': MONTHS,
        'form_errors': form_errors,
    })


def slip_detail(request, slip_pk):
    """View a single payslip in a formatted, print-friendly layout."""
    target_slip = get_object_or_404(Payslip, pk=slip_pk)
    return render(request, 'payroll_app/payslip_detail.html', {
        'slip': target_slip,
    })
