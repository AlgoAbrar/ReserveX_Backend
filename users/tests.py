from django.test import TestCase

# Create your tests here.
# -------------------------------
# 🔹 MOCK DATABASE
# -------------------------------
reservations = []
payments = []
orders = []

# -------------------------------
# 🔹 API FUNCTIONS (SIMULATION)
# -------------------------------

def create_reservation(data):
    if not data.get("customer_name"):
        return {"status": 400, "message": "Invalid data"}

    data["id"] = len(reservations) + 1
    reservations.append(data)
    return {"status": 201, "data": data}


def get_reservations():
    return {"status": 200, "data": reservations}


def update_reservation(res_id, new_data):
    for r in reservations:
        if r["id"] == res_id:
            r.update(new_data)
            return {"status": 200, "data": r}
    return {"status": 404, "message": "Not found"}


def delete_reservation(res_id):
    for r in reservations:
        if r["id"] == res_id:
            reservations.remove(r)
            return {"status": 204}
    return {"status": 404}


# -------------------------------
# PAYMENT
# -------------------------------

def create_payment(data):
    if "amount" not in data:
        return {"status": 400}

    data["id"] = len(payments) + 1
    payments.append(data)
    return {"status": 201, "data": data}


# -------------------------------
# ORDER
# -------------------------------

def create_order(data):
    if "reservation" not in data:
        return {"status": 400}

    data["id"] = len(orders) + 1
    orders.append(data)
    return {"status": 201, "data": data}


# -------------------------------
# 🔹 TESTING FUNCTIONS
# -------------------------------

def test_create_reservation():
    res = create_reservation({
        "customer_name": "Rafid",
        "table_number": 5
    })
    assert res["status"] == 201


def test_get_reservations():
    res = get_reservations()
    assert res["status"] == 200


def test_update_reservation():
    create_reservation({"customer_name": "Test"})
    res = update_reservation(1, {"customer_name": "Updated"})
    assert res["status"] == 200


def test_delete_reservation():
    create_reservation({"customer_name": "Delete"})
    res = delete_reservation(1)
    assert res["status"] == 204


def test_invalid_payment():
    res = create_payment({"method": "Cash"})
    assert res["status"] == 400


def test_create_order():
    create_reservation({"customer_name": "Order User"})
    res = create_order({"reservation": 1})
    assert res["status"] == 201


def test_not_found():
    res = update_reservation(999, {"name": "X"})
    assert res["status"] == 404


# -------------------------------
# 🔹 RUN ALL TESTS
# -------------------------------

def run_tests():
    test_create_reservation()
    test_get_reservations()
    test_update_reservation()
    test_delete_reservation()
    test_invalid_payment()
    test_create_order()
    test_not_found()

    print("✅ All tests passed successfully!")


if __name__ == "__main__":
    run_tests()