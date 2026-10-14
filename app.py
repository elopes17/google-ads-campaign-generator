from flask import Flask, abort, redirect, render_template, request, send_file, url_for

from demo_data import demo_form_data, is_approved_demo_payload
from generator import generate_campaign
from google_ads_editor_export import (
    EditorExportError, ZIP_MIMETYPE as EDITOR_ZIP_MIMETYPE,
    build_editor_package, editor_export_filename,
)
from landing_page_export import ZIP_MIMETYPE, build_landing_pages_zip, landing_pages_filename
from landing_pages import generate_landing_pages
from rules_library import RULES
from validation import SERVICES, validate_intake

app = Flask(__name__)
app.config['DEBUG'] = False


def summarize_plan(plan):
    """Return display-only counts from the generated campaign plan."""
    sections = {section['id']: section['rows'] for section in plan['sections']}
    structure = sections['campaign-structure']
    return {
        'campaigns': len({row[0] for row in structure}),
        'ad_groups': len(structure),
        'keywords': len(sections['keywords']),
        'negative_keywords': len(sections['negative-keywords']),
        'responsive_search_ads': len(plan['ads']),
    }


def render_campaign_results(data, demo_mode=False):
    """Render one validated result using the same context for normal and demo flows."""
    plan = generate_campaign(data)
    return render_template(
        'results.html',
        form=data,
        selected_services=data['services'],
        plan=plan,
        plan_summary=summarize_plan(plan),
        preview_pages=[
            {'service': service, 'slug': rule['path'].lstrip('/')}
            for service, rule in RULES.items() if service in data['services']
        ],
        demo_mode=demo_mode,
    )


@app.route("/", methods=["GET", "POST"])
@app.route("/generate", methods=["GET", "POST"], endpoint="generate")
def intake():
    if request.path == "/generate" and request.method == "GET":
        return redirect(url_for("intake"))

    error = None
    selected_services = []

    if request.method == "POST":
        data, errors = validate_intake(request.form)
        selected_services = data['services']
        if errors:
            error = ' '.join(errors)
        else:
            return render_campaign_results(data)

    return render_template(
        "intake.html",
        services=SERVICES,
        selected_services=selected_services,
        form=request.form,
        error=error,
    ), 400 if error else 200


@app.route('/demo', methods=['GET'])
def demo():
    """Render a complete result from fixed fictional portfolio data."""
    data, errors = validate_intake(demo_form_data())
    if errors:
        raise RuntimeError('The fixed fictional demo data is invalid.')
    return render_campaign_results(data, demo_mode=True)


@app.route('/preview/<service_slug>', methods=['GET', 'POST'])
def preview(service_slug):
    service = next((name for name, rule in RULES.items()
                    if rule['path'].lstrip('/') == service_slug), None)
    if request.method == 'GET':
        if service is None:
            abort(404)
        return redirect(url_for('intake'))

    data, errors = validate_intake(request.form)
    if errors:
        return render_template(
            'intake.html', services=SERVICES, selected_services=data['services'],
            form=request.form, error=' '.join(errors),
        ), 400
    if service is None or service not in data['services']:
        abort(404)
    # Detect the immutable demo from the complete validated payload before
    # narrowing generation to the requested selected page.
    demo_mode = is_approved_demo_payload(data)
    page = generate_landing_pages(
        {**data, 'services': [service]}, demo_mode=demo_mode,
    )[0]
    return render_template('landing_page.html', page=page)


@app.route('/export', methods=['POST'])
def export():
    data, errors = validate_intake(request.form)
    if errors:
        return render_template(
            'intake.html', services=SERVICES, selected_services=data['services'],
            form=request.form, error=' '.join(errors),
        ), 400
    from excel_export import build_workbook, export_filename, XLSX_MIMETYPE

    plan = generate_campaign(data)
    return send_file(
        build_workbook(data, plan), mimetype=XLSX_MIMETYPE,
        as_attachment=True, download_name=export_filename(data['business_name']),
    )


@app.route('/export/landing-pages', methods=['POST'])
def export_landing_pages():
    data, errors = validate_intake(request.form)
    if errors:
        return render_template(
            'intake.html', services=SERVICES, selected_services=data['services'],
            form=request.form, error=' '.join(errors),
        ), 400
    pages = generate_landing_pages(data)
    return send_file(
        build_landing_pages_zip(data, pages), mimetype=ZIP_MIMETYPE,
        as_attachment=True, download_name=landing_pages_filename(data['business_name']),
    )


@app.route('/export/google-ads-editor', methods=['POST'])
def export_google_ads_editor():
    data, errors = validate_intake(request.form)
    if not data.get('website_url'):
        errors.append('Business website base URL is required for Google Ads Editor export.')
    if errors:
        return render_template(
            'intake.html', services=SERVICES, selected_services=data['services'],
            form=request.form, error=' '.join(errors),
        ), 400
    plan = generate_campaign(data)
    try:
        package = build_editor_package(data, plan)
    except EditorExportError as error:
        # Do not reflect a rejected spreadsheet value back into the error page.
        return render_template(
            'intake.html', services=SERVICES, selected_services=data['services'],
            form={}, error=str(error),
        ), 400
    return send_file(
        package, mimetype=EDITOR_ZIP_MIMETYPE, as_attachment=True,
        download_name=editor_export_filename(data['business_name']),
    )


if __name__ == "__main__":
    app.run(debug=False)
