from wtforms.validators import DataRequired

from quirck.core.form import AceEditorField, QuirckForm


class ReportForm(QuirckForm):
    report = AceEditorField(label="", validators=[DataRequired()])


__all__ = ["ReportForm"]
