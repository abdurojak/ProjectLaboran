ADMIN_ROLE = 'admin'
LABORAN_ROLE = 'laboran'
ASISTEN_LAB_ROLE = 'asisten_lab'
MAHASISWA_ROLE = 'mahasiswa'

ADMIN_SYSTEM_ROLES = {ADMIN_ROLE}
LAB_OPERATIONS_ROLES = {LABORAN_ROLE}
PRAKTIKUM_ROLES = {LABORAN_ROLE, ASISTEN_LAB_ROLE}
BORROWER_ROLES = {MAHASISWA_ROLE, ASISTEN_LAB_ROLE}


def has_role(pengguna, roles):
    return bool(pengguna and pengguna.role in roles)


def is_admin(pengguna):
    return has_role(pengguna, ADMIN_SYSTEM_ROLES)


def is_laboran(pengguna):
    return has_role(pengguna, LAB_OPERATIONS_ROLES)


def can_manage_lab_operations(pengguna):
    return is_laboran(pengguna)


def can_manage_praktikum(pengguna):
    return has_role(pengguna, PRAKTIKUM_ROLES)


def can_borrow_items(pengguna):
    return has_role(pengguna, BORROWER_ROLES)
