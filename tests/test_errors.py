from wagtail_mcp.errors import APIError, format_api_error


def problem(**kw):
    base = {
        "type": "about:blank",
        "title": "Unprocessable Entity",
        "status": 422,
        "detail": "Validation failed",
    }
    return {**base, **kw}


def test_validation_errors_flattened():
    err = APIError(
        422, problem(errors=[{"loc": ["body", "title"], "msg": "field required"}])
    )
    msg = format_api_error(err)
    assert "Unprocessable Entity (422)" in msg
    assert "body.title: field required" in msg


def test_404_hint():
    err = APIError(
        404,
        {
            "type": "about:blank",
            "title": "Not Found",
            "status": 404,
            "detail": "No Page matches",
        },
    )
    msg = format_api_error(err)
    assert "list the parent collection" in msg


def test_401_hint_and_403_hint():
    assert "API token" in format_api_error(
        APIError(401, {"title": "Unauthorized", "status": 401})
    )
    assert "permission" in format_api_error(
        APIError(403, {"title": "Forbidden", "status": 403})
    )


def test_multiple_validation_errors_all_rendered():
    err = APIError(
        422,
        problem(
            errors=[
                {"loc": ["body", "title"], "msg": "field required"},
                {"loc": ["body", "slug"], "msg": "field required"},
            ]
        ),
    )
    msg = format_api_error(err)
    assert "body.title: field required" in msg
    assert "body.slug: field required" in msg


def test_error_without_detail_and_without_errors():
    err = APIError(
        500, {"type": "about:blank", "title": "Internal Server Error", "status": 500}
    )
    msg = format_api_error(err)
    assert msg == "Internal Server Error (500)"


def test_error_missing_title_uses_status_only():
    err = APIError(418, {"status": 418, "detail": "teapot"})
    msg = format_api_error(err)
    assert "(418)" in msg
    assert "teapot" in msg


def test_error_with_non_string_detail():
    err = APIError(422, problem(detail=123))
    msg = format_api_error(err)
    # detail=123 is not a string; formatter must coerce it, not crash.
    assert "123" in msg


def test_error_entry_with_str_errors_list():
    # Pydantic errors may have a scalar `errors`; guard against iterating a string.
    err = APIError(422, problem(errors="not-a-list"))
    msg = format_api_error(err)
    # Falls back to detail only, no crash.
    assert "Validation failed" in msg


def test_api_error_exposes_attrs():
    problem_dict = problem(errors=[])
    err = APIError(422, problem_dict)
    assert err.status == 422
    assert err.problem is problem_dict
