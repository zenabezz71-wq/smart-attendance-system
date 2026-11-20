from rest_framework import serializers

from . import models as m


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = m.User
        fields = ["id", "username", "first_name", "last_name", "email", "role", "password", "is_active"]

    def create(self, validated):
        pw = validated.pop("password", None)
        user = m.User(**validated)
        user.set_password(pw) if pw else user.set_unusable_password()
        user.save()
        return user

    def update(self, inst, validated):
        pw = validated.pop("password", None)
        for k, v in validated.items():
            setattr(inst, k, v)
        if pw:
            inst.set_password(pw)
        inst.save()
        return inst


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = m.Student
        fields = ["id", "user", "student_id", "full_name", "nfc_tag_id", "department", "level"]


class DoctorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = m.Doctor
        fields = ["id", "user", "doctor_id", "full_name", "department"]


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Course
        fields = "__all__"


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Room
        fields = "__all__"


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Device
        fields = ["id", "device_code", "room", "status", "api_key", "last_seen"]
        read_only_fields = ["last_seen"]


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Schedule
        fields = "__all__"


class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Enrollment
        fields = "__all__"


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = m.Attendance
        fields = ["id", "student", "student_name", "course", "schedule", "device", "date", "timestamp", "status"]


class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Grade
        fields = "__all__"
        read_only_fields = ["doctor"]


class BehaviorSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Behavior
        fields = "__all__"
        read_only_fields = ["doctor"]


class BonusSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.Bonus
        fields = "__all__"
        read_only_fields = ["doctor"]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = m.AuditLog
        fields = "__all__"


class ScanSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=30)
    card_uid = serializers.CharField(max_length=32)
    timestamp = serializers.DateTimeField(required=False)
