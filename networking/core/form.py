from wtforms.validators import DataRequired

from quirck.core.form import AceEditorField, QuirckForm


class ReportForm(QuirckForm):
    report = AceEditorField(label="", validators=[DataRequired()])


class ClearProgressForm(QuirckForm):
    pass


__all__ = ["ReportForm", "ClearProgressForm"]
