class RoleType:
    SUPERADMIN = 0
    ADMIN = 1  # Admin (all permissions)
    CREATOR = 2  # Creator (creative generator only)
    SCHEDULER = 3  # Scheduler (creative generator + auto scheduler + auto optimize)

    CHOICES = ((SUPERADMIN, "superadmin"), (ADMIN, "admin"), (CREATOR, "creator"), (SCHEDULER, "scheduler"))


class GenderType:
    OTHERS = 0
    MALE = 1
    FEMALE = 2

    CHOICES = (
        (OTHERS, "others"),
        (MALE, "male"),
        (FEMALE, "female"),
    )


class AdAccountActiveType:
    NO = 0
    Pending = 1
    Yes = 2

    CHOICES = (
        (NO, "no"),
        (Pending, "pending"),
        (Yes, "yes"),
    )


class CreativeType:
    VIDEO = "Video"
    IMAGE = "Image"
    SPARK = "Spark"

    CHOICES = ((VIDEO, "Video"), (IMAGE, "Image"), (SPARK, "Spark"))


class PlacementType:
    POST = "Post"
    STORY = "Story"
    REELS = "Reels"

    CHOICES = ((POST, "Post"), (STORY, "Story"), (REELS, "Reels"))

class SocialAccountType:
    NORMAL = 0
    GOOGLE = 1
    APPLE = 2
    AMAZON = 3

    CHOICES = (
        (NORMAL, "normal"),
        (GOOGLE, "google"),
        (APPLE, "apple"),
        (AMAZON, "amazon"),
    )


class Org_Role:
    CREATOR = 3
    MANAGER = 4

    CHOICES = (
        (CREATOR, "creator"),
        (MANAGER, "manager"),
    )