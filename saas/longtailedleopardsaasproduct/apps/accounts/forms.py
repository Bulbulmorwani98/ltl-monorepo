import re

from django import forms


class ResetPasswordForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "New Password"}),
        label="New Password",
        required=True,
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm Password"}),
        label="Confirm Password",
        required=True,
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        # Check if the two passwords match
        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        if not re.match(
            r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$",
            password,
        ):
            raise forms.ValidationError(
                "Password must contain at least 8 characters, including one uppercase letter, one lowercase letter, one number, and one special character."
            )

        return cleaned_data
