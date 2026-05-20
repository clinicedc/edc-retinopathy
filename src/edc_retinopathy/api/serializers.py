from __future__ import annotations

from rest_framework import serializers

from ..models import RetinalImage, RetinopathyResult


class RetinopathyResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = RetinopathyResult
        fields = [
            "id",
            "subject_identifier",
            "image_date",
            "eye",
            "grading",
            "analysis_data",
            "device_id",
            "site_id",
            "received_datetime",
        ]
        read_only_fields = ["id", "received_datetime"]


class RetinalImageSerializer(serializers.Serializer):
    """Handles multipart image upload linked to a RetinopathyResult."""

    result_id = serializers.IntegerField(
        help_text="ID of the RetinopathyResult this image belongs to.",
    )
    eye = serializers.ChoiceField(
        choices=RetinalImage.eye.field.choices,
        help_text="Which eye: L, R, or B.",
    )
    image = serializers.ImageField(
        help_text="The retinal image file.",
    )

    def validate_result_id(self, value: int) -> int:
        if not RetinopathyResult.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                f"RetinopathyResult with id={value} does not exist."
            )
        return value
