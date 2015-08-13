
# the different review states for an activity
# no changes have yet been made to the activity
REVIEW_STATE_FRESH = u'fresh'
# there are un-reviewed edits in the activity (or no edits at all)
REVIEW_STATE_EDITED = u'unreviewed edits'
# there are un-reviewed edits in the activity and a review has been requested
REVIEW_STATE_FEEDBACK = u'feedback requested'
# a review has happened and the site is ready to be published
REVIEW_STATE_ENDORSED = u'edits endorsed'
# the site has been published
REVIEW_STATE_PUBLISHED = u'changes published'

# the different working states for an activity
# the activity is current and active
WORKING_STATE_ACTIVE = u'active'
# the activity has been published
WORKING_STATE_PUBLISHED = u'published'
# the activity has been deleted
WORKING_STATE_DELETED = u'deleted'

# the different categories and types of messages that can be displayed in the activity overview
# info messages, like starting an activity or changing its review or working state
COMMIT_CATEGORY_INFO = u'info'
COMMIT_TYPE_ACTIVITY_UPDATE = u'activity update'
COMMIT_TYPE_REVIEW_UPDATE = u'review update'
# edit messages, like creating or editing topics and articles
COMMIT_CATEGORY_EDIT = u'edit'
COMMIT_TYPE_EDIT = u'edit'
# comment messages, for leaving comments
COMMIT_CATEGORY_COMMENT = u'comment'
COMMIT_TYPE_COMMENT = u'comment'

# ISO language codes
ISO_CODE_ENGLISH = 'en'
ISO_NAME_ENGLISH = 'English'
