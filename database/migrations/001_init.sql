-- Moodwave schema generated from SQLAlchemy metadata (SQLite).
-- Base tables from the generated DDL plus extensions required by features:
-- notification_archive, event_archive, tracks, emotion_logs, idempotency_keys, etc.
PRAGMA foreign_keys = ON;

-- table: attachments
CREATE TABLE attachments (
	id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	biz_type VARCHAR(50) NOT NULL, 
	biz_id VARCHAR(64), 
	url TEXT NOT NULL, 
	thumb_url TEXT, 
	detail_url TEXT, 
	storage_key TEXT, 
	mime VARCHAR(100) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	width INTEGER NOT NULL, 
	height INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE
);

-- table: audit_logs
CREATE TABLE audit_logs (
	id INTEGER NOT NULL, 
	actor_id INTEGER, 
	action VARCHAR(100) NOT NULL, 
	target_type VARCHAR(50) NOT NULL, 
	target_id VARCHAR(64) NOT NULL, 
	detail JSON, 
	ip VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);

-- table: banners
CREATE TABLE banners (
	id INTEGER NOT NULL, 
	position INTEGER NOT NULL, 
	position_code VARCHAR(50) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	subtitle TEXT, 
	image_url TEXT NOT NULL, 
	link_url TEXT, 
	sort INTEGER NOT NULL, 
	start_at DATETIME, 
	end_at DATETIME, 
	status VARCHAR(50) NOT NULL, 
	aspect_ratio VARCHAR(20) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

-- table: categories
CREATE TABLE categories (
	id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	slug VARCHAR(255) NOT NULL, 
	parent_id INTEGER, 
	sort INTEGER NOT NULL, 
	post_count INTEGER NOT NULL, 
	description TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_categories_slug UNIQUE (slug), 
	FOREIGN KEY(parent_id) REFERENCES categories (id) ON DELETE SET NULL
);

-- table: client_logs
CREATE TABLE client_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	level VARCHAR(20) NOT NULL, 
	message TEXT NOT NULL, 
	stack TEXT, 
	route VARCHAR(255), 
	user_agent TEXT, 
	request_id VARCHAR(64), 
	context JSON, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

-- table: daily_metrics
CREATE TABLE daily_metrics (
	id INTEGER NOT NULL, 
	day DATE NOT NULL, 
	metric VARCHAR(100) NOT NULL, 
	dimension VARCHAR(100) NOT NULL, 
	value INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_daily_metric UNIQUE (day, metric, dimension)
);

-- table: email_logs
CREATE TABLE email_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	to_email VARCHAR(255) NOT NULL, 
	template VARCHAR(100) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	error_message TEXT, 
	sent_at DATETIME, 
	retry_count INTEGER NOT NULL, 
	context JSON, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

-- table: emotion_logs
CREATE TABLE emotion_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	emotion VARCHAR(50) NOT NULL, 
	confidence FLOAT NOT NULL, 
	scores JSON NOT NULL, 
	source VARCHAR(50) NOT NULL, 
	inference_ms INTEGER NOT NULL, 
	image_attachment_id INTEGER, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(image_attachment_id) REFERENCES attachments (id) ON DELETE SET NULL
);

-- table: event_archive
CREATE TABLE event_archive (
	id INTEGER NOT NULL, 
	original_id INTEGER NOT NULL, 
	event_key VARCHAR(255) NOT NULL, 
	user_hash VARCHAR(64), 
	session_id VARCHAR(64) NOT NULL, 
	props JSON, 
	occurred_at DATETIME NOT NULL, 
	archived_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

-- table: event_defs
CREATE TABLE event_defs (
	id INTEGER NOT NULL, 
	"key" VARCHAR(255) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	props_schema JSON, 
	status VARCHAR(50) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE ("key")
);

-- table: events
CREATE TABLE events (
	id INTEGER NOT NULL, 
	event_key VARCHAR(255) NOT NULL, 
	user_id INTEGER, 
	user_hash VARCHAR(64), 
	session_id VARCHAR(64) NOT NULL, 
	page INTEGER NOT NULL, 
	props JSON, 
	occurred_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

-- table: favorite_tracks
CREATE TABLE favorite_tracks (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	track_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_favorite_user_track UNIQUE (user_id, track_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(track_id) REFERENCES tracks (id) ON DELETE CASCADE
);

-- table: feedbacks
CREATE TABLE feedbacks (
	id INTEGER NOT NULL, 
	ticket_no VARCHAR(32) NOT NULL, 
	user_id INTEGER NOT NULL, 
	type VARCHAR(50) NOT NULL, 
	content TEXT NOT NULL, 
	images JSON, 
	contact VARCHAR(255), 
	status VARCHAR(50) NOT NULL, 
	handler_id INTEGER, 
	reply TEXT, 
	supplementary JSON, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (ticket_no), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(handler_id) REFERENCES users (id) ON DELETE SET NULL
);

-- table: funnels
CREATE TABLE funnels (
	id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	steps JSON NOT NULL, 
	created_by INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE CASCADE
);

-- table: idempotency_keys
CREATE TABLE idempotency_keys (
	"key" VARCHAR(255) NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	response_status INTEGER NOT NULL, 
	response_body TEXT, 
	response_headers JSON, 
	created_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY ("key")
);

-- table: invite_codes
CREATE TABLE invite_codes (
	id INTEGER NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	created_by INTEGER NOT NULL, 
	used_by INTEGER, 
	expires_at DATETIME, 
	consumed_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(used_by) REFERENCES users (id) ON DELETE SET NULL
);

-- table: items
CREATE TABLE items (
	id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	content TEXT NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	category_id INTEGER, 
	cover_url TEXT, 
	cover_thumb_url TEXT, 
	deleted_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE SET NULL
);

-- table: notification_archive
CREATE TABLE notification_archive (
	id INTEGER NOT NULL, 
	original_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	type VARCHAR(50) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	message TEXT NOT NULL, 
	read_at DATETIME, 
	archived_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- table: notifications
CREATE TABLE notifications (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	type VARCHAR(50) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	message TEXT NOT NULL, 
	payload JSON, 
	target_type VARCHAR(50) NOT NULL, 
	target_id VARCHAR(64) NOT NULL, 
	read_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_notifications_dedup UNIQUE (user_id, target_type, target_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- table: o_auth_accounts
CREATE TABLE o_auth_accounts (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	provider VARCHAR(50) NOT NULL, 
	provider_user_id INTEGER, 
	provider_uid VARCHAR(255) NOT NULL, 
	provider_email VARCHAR(255), 
	access_token TEXT, 
	avatar_url TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_oauth_provider_uid UNIQUE (provider, provider_uid), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- table: oauth_states
CREATE TABLE oauth_states (
	id INTEGER NOT NULL, 
	state VARCHAR(128) NOT NULL, 
	provider VARCHAR(50) NOT NULL, 
	bind_user_id INTEGER, 
	expires_at DATETIME NOT NULL, 
	used_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (state), 
	FOREIGN KEY(bind_user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- table: password_resets
CREATE TABLE password_resets (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR(255) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	used_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- table: post_tags
CREATE TABLE post_tags (
	id INTEGER NOT NULL, 
	post_id VARCHAR(64) NOT NULL, 
	tag_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_post_tags_post_tag UNIQUE (post_id, tag_id), 
	FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

-- table: push_channels
CREATE TABLE push_channels (
	id INTEGER NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	provider VARCHAR(50) NOT NULL, 
	config JSON, 
	status VARCHAR(50) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

-- table: push_tasks
CREATE TABLE push_tasks (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	channel_code VARCHAR(50) NOT NULL, 
	template_code VARCHAR(100) NOT NULL, 
	payload JSON, 
	status VARCHAR(50) NOT NULL, 
	retry_count INTEGER NOT NULL, 
	sent_at DATETIME, 
	error_message TEXT, 
	is_marketing BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- table: rate_limit_counters
CREATE TABLE rate_limit_counters (
	"key" VARCHAR(255) NOT NULL, 
	window_start INTEGER NOT NULL, 
	count INTEGER NOT NULL, 
	PRIMARY KEY ("key", window_start)
);

-- table: recommendation_logs
CREATE TABLE recommendation_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	emotion VARCHAR(50) NOT NULL, 
	track_id INTEGER NOT NULL, 
	score FLOAT NOT NULL, 
	reason TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(track_id) REFERENCES tracks (id) ON DELETE CASCADE
);

-- table: refresh_tokens
CREATE TABLE refresh_tokens (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR(255) NOT NULL, 
	user_agent VARCHAR(255) NOT NULL, 
	ip VARCHAR(255) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	revoked_at DATETIME, 
	last_used_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- table: roles
CREATE TABLE roles (
	id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	permissions JSON NOT NULL, 
	description TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

-- table: search_logs
CREATE TABLE search_logs (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	keyword VARCHAR(255) NOT NULL, 
	result_count INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);

-- table: share_links
CREATE TABLE share_links (
	id INTEGER NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	target_type VARCHAR(50) NOT NULL, 
	target_id VARCHAR(64) NOT NULL, 
	created_by INTEGER NOT NULL, 
	expires_at DATETIME, 
	view_count INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_share_links_code UNIQUE (code), 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE CASCADE
);

-- table: sms_logs
CREATE TABLE sms_logs (
	id INTEGER NOT NULL, 
	phone VARCHAR(32) NOT NULL, 
	scene VARCHAR(50) NOT NULL, 
	template_id VARCHAR(64) NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	error_message TEXT, 
	sent_at DATETIME, 
	ip VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

-- table: tags
CREATE TABLE tags (
	id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	slug VARCHAR(255) NOT NULL, 
	post_count INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_tags_slug UNIQUE (slug)
);

-- table: track_feedback
CREATE TABLE track_feedback (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	track_id INTEGER NOT NULL, 
	rating INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_track_feedback_user_track UNIQUE (user_id, track_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(track_id) REFERENCES tracks (id) ON DELETE CASCADE
);

-- table: tracks
CREATE TABLE tracks (
	id INTEGER NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	artist VARCHAR(255) NOT NULL, 
	album VARCHAR(255), 
	mood VARCHAR(50) NOT NULL, 
	mood_scores JSON NOT NULL, 
	audio_features JSON NOT NULL, 
	local_path TEXT, 
	preview_url TEXT, 
	cover_url TEXT, 
	duration_seconds FLOAT NOT NULL, 
	source VARCHAR(50) NOT NULL, 
	external_id VARCHAR(255), 
	is_public BOOLEAN NOT NULL, 
	play_count INTEGER NOT NULL, 
	like_count INTEGER NOT NULL, 
	license_note TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

-- table: user_push_settings
CREATE TABLE user_push_settings (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	channel_code VARCHAR(50) NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	quiet_hours BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_user_push_channel UNIQUE (user_id, channel_code), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- table: user_roles
CREATE TABLE user_roles (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	granted_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_user_roles_user_role UNIQUE (user_id, role_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);

-- table: users
CREATE TABLE users (
	id INTEGER NOT NULL, 
	email VARCHAR(255), 
	password_hash VARCHAR(255), 
	nickname VARCHAR(255) NOT NULL, 
	role VARCHAR(50) NOT NULL, 
	avatar_url TEXT, 
	status VARCHAR(50) NOT NULL, 
	last_login_at DATETIME, 
	bio TEXT, 
	phone VARCHAR(32), 
	gender VARCHAR(50) NOT NULL, 
	birthday DATE, 
	location TEXT, 
	locale VARCHAR(50) NOT NULL, 
	email_verified BOOLEAN NOT NULL, 
	phone_verified BOOLEAN NOT NULL, 
	unread_count INTEGER NOT NULL, 
	failed_login_attempts INTEGER NOT NULL, 
	locked_until DATETIME, 
	disabled_reason TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (phone)
);

-- table: verify_codes
CREATE TABLE verify_codes (
	id INTEGER NOT NULL, 
	target VARCHAR(255) NOT NULL, 
	scene VARCHAR(50) NOT NULL, 
	code_hash VARCHAR(255) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	used_at DATETIME, 
	ip VARCHAR(64) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

-- index: ix_attachments_created_at
CREATE INDEX ix_attachments_created_at ON attachments (created_at);

-- index: ix_attachments_owner_id
CREATE INDEX ix_attachments_owner_id ON attachments (owner_id);

-- index: ix_audit_logs_actor_id
CREATE INDEX ix_audit_logs_actor_id ON audit_logs (actor_id);

-- index: ix_audit_logs_created_at
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

-- index: ix_banners_created_at
CREATE INDEX ix_banners_created_at ON banners (created_at);

-- index: ix_banners_position_code
CREATE INDEX ix_banners_position_code ON banners (position_code);

-- index: ix_banners_position_sort
CREATE INDEX ix_banners_position_sort ON banners (position, sort);

-- index: ix_banners_status
CREATE INDEX ix_banners_status ON banners (status);

-- index: ix_categories_created_at
CREATE INDEX ix_categories_created_at ON categories (created_at);

-- index: ix_categories_parent_id
CREATE INDEX ix_categories_parent_id ON categories (parent_id);

-- index: ix_client_logs_created_at
CREATE INDEX ix_client_logs_created_at ON client_logs (created_at);

-- index: ix_daily_metrics_day
CREATE INDEX ix_daily_metrics_day ON daily_metrics (day);

-- index: ix_email_logs_created_at
CREATE INDEX ix_email_logs_created_at ON email_logs (created_at);

-- index: ix_email_logs_status
CREATE INDEX ix_email_logs_status ON email_logs (status);

-- index: ix_email_logs_user_id
CREATE INDEX ix_email_logs_user_id ON email_logs (user_id);

-- index: ix_emotion_logs_created_at
CREATE INDEX ix_emotion_logs_created_at ON emotion_logs (created_at);

-- index: ix_emotion_logs_emotion
CREATE INDEX ix_emotion_logs_emotion ON emotion_logs (emotion);

-- index: ix_emotion_logs_user_id
CREATE INDEX ix_emotion_logs_user_id ON emotion_logs (user_id);

-- index: ix_event_archive_created_at
CREATE INDEX ix_event_archive_created_at ON event_archive (created_at);

-- index: ix_event_archive_occurred_at
CREATE INDEX ix_event_archive_occurred_at ON event_archive (occurred_at);

-- index: ix_event_defs_created_at
CREATE INDEX ix_event_defs_created_at ON event_defs (created_at);

-- index: ix_events_created_at
CREATE INDEX ix_events_created_at ON events (created_at);

-- index: ix_events_event_key
CREATE INDEX ix_events_event_key ON events (event_key);

-- index: ix_events_occurred_at
CREATE INDEX ix_events_occurred_at ON events (occurred_at);

-- index: ix_events_session_id
CREATE INDEX ix_events_session_id ON events (session_id);

-- index: ix_events_user_hash
CREATE INDEX ix_events_user_hash ON events (user_hash);

-- index: ix_events_user_id
CREATE INDEX ix_events_user_id ON events (user_id);

-- index: ix_favorite_tracks_created_at
CREATE INDEX ix_favorite_tracks_created_at ON favorite_tracks (created_at);

-- index: ix_feedbacks_created_at
CREATE INDEX ix_feedbacks_created_at ON feedbacks (created_at);

-- index: ix_feedbacks_handler_id
CREATE INDEX ix_feedbacks_handler_id ON feedbacks (handler_id);

-- index: ix_feedbacks_status
CREATE INDEX ix_feedbacks_status ON feedbacks (status);

-- index: ix_feedbacks_user_id
CREATE INDEX ix_feedbacks_user_id ON feedbacks (user_id);

-- index: ix_funnels_created_at
CREATE INDEX ix_funnels_created_at ON funnels (created_at);

-- index: ix_funnels_created_by
CREATE INDEX ix_funnels_created_by ON funnels (created_by);

-- index: ix_idempotency_expires
CREATE INDEX ix_idempotency_expires ON idempotency_keys (expires_at);

-- index: ix_invite_codes_created_at
CREATE INDEX ix_invite_codes_created_at ON invite_codes (created_at);

-- index: ix_invite_codes_created_by
CREATE INDEX ix_invite_codes_created_by ON invite_codes (created_by);

-- index: ix_invite_codes_used_by
CREATE INDEX ix_invite_codes_used_by ON invite_codes (used_by);

-- index: ix_items_category_id
CREATE INDEX ix_items_category_id ON items (category_id);

-- index: ix_items_created_at
CREATE INDEX ix_items_created_at ON items (created_at);

-- index: ix_items_deleted_at
CREATE INDEX ix_items_deleted_at ON items (deleted_at);

-- index: ix_items_owner_id
CREATE INDEX ix_items_owner_id ON items (owner_id);

-- index: ix_items_status
CREATE INDEX ix_items_status ON items (status);

-- index: ix_notification_archive_created_at
CREATE INDEX ix_notification_archive_created_at ON notification_archive (created_at);

-- index: ix_notification_archive_user_id
CREATE INDEX ix_notification_archive_user_id ON notification_archive (user_id);

-- index: ix_notifications_created_at
CREATE INDEX ix_notifications_created_at ON notifications (created_at);

-- index: ix_notifications_type
CREATE INDEX ix_notifications_type ON notifications (type);

-- index: ix_notifications_user_id
CREATE INDEX ix_notifications_user_id ON notifications (user_id);

-- index: ix_o_auth_accounts_created_at
CREATE INDEX ix_o_auth_accounts_created_at ON o_auth_accounts (created_at);

-- index: ix_o_auth_accounts_user_id
CREATE INDEX ix_o_auth_accounts_user_id ON o_auth_accounts (user_id);

-- index: ix_oauth_states_created_at
CREATE INDEX ix_oauth_states_created_at ON oauth_states (created_at);

-- index: ix_password_resets_created_at
CREATE INDEX ix_password_resets_created_at ON password_resets (created_at);

-- index: ix_password_resets_token_hash
CREATE INDEX ix_password_resets_token_hash ON password_resets (token_hash);

-- index: ix_password_resets_user_id
CREATE INDEX ix_password_resets_user_id ON password_resets (user_id);

-- index: ix_post_tags_created_at
CREATE INDEX ix_post_tags_created_at ON post_tags (created_at);

-- index: ix_post_tags_post_id
CREATE INDEX ix_post_tags_post_id ON post_tags (post_id);

-- index: ix_post_tags_tag_id
CREATE INDEX ix_post_tags_tag_id ON post_tags (tag_id);

-- index: ix_push_channels_created_at
CREATE INDEX ix_push_channels_created_at ON push_channels (created_at);

-- index: ix_push_tasks_created_at
CREATE INDEX ix_push_tasks_created_at ON push_tasks (created_at);

-- index: ix_push_tasks_user_id
CREATE INDEX ix_push_tasks_user_id ON push_tasks (user_id);

-- index: ix_rate_limit_window
CREATE INDEX ix_rate_limit_window ON rate_limit_counters (window_start);

-- index: ix_recommendation_logs_created_at
CREATE INDEX ix_recommendation_logs_created_at ON recommendation_logs (created_at);

-- index: ix_recommendation_logs_user_id
CREATE INDEX ix_recommendation_logs_user_id ON recommendation_logs (user_id);

-- index: ix_refresh_tokens_created_at
CREATE INDEX ix_refresh_tokens_created_at ON refresh_tokens (created_at);

-- index: ix_refresh_tokens_hash
CREATE INDEX ix_refresh_tokens_hash ON refresh_tokens (token_hash);

-- index: ix_refresh_tokens_user_id
CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);

-- index: ix_roles_created_at
CREATE INDEX ix_roles_created_at ON roles (created_at);

-- index: ix_search_logs_created_at
CREATE INDEX ix_search_logs_created_at ON search_logs (created_at);

-- index: ix_search_logs_keyword
CREATE INDEX ix_search_logs_keyword ON search_logs (keyword);

-- index: ix_search_logs_user_id
CREATE INDEX ix_search_logs_user_id ON search_logs (user_id);

-- index: ix_share_links_created_at
CREATE INDEX ix_share_links_created_at ON share_links (created_at);

-- index: ix_share_links_created_by
CREATE INDEX ix_share_links_created_by ON share_links (created_by);

-- index: ix_sms_logs_created_at
CREATE INDEX ix_sms_logs_created_at ON sms_logs (created_at);

-- index: ix_sms_logs_phone
CREATE INDEX ix_sms_logs_phone ON sms_logs (phone);

-- index: ix_tags_created_at
CREATE INDEX ix_tags_created_at ON tags (created_at);

-- index: ix_tags_post_count
CREATE INDEX ix_tags_post_count ON tags (post_count);

-- index: ix_track_feedback_created_at
CREATE INDEX ix_track_feedback_created_at ON track_feedback (created_at);

-- index: ix_tracks_created_at
CREATE INDEX ix_tracks_created_at ON tracks (created_at);

-- index: ix_tracks_mood
CREATE INDEX ix_tracks_mood ON tracks (mood);

-- index: ix_tracks_source
CREATE INDEX ix_tracks_source ON tracks (source);

-- index: ix_user_push_settings_created_at
CREATE INDEX ix_user_push_settings_created_at ON user_push_settings (created_at);

-- index: ix_user_push_settings_user_id
CREATE INDEX ix_user_push_settings_user_id ON user_push_settings (user_id);

-- index: ix_user_roles_created_at
CREATE INDEX ix_user_roles_created_at ON user_roles (created_at);

-- index: ix_user_roles_role_id
CREATE INDEX ix_user_roles_role_id ON user_roles (role_id);

-- index: ix_user_roles_user_id
CREATE INDEX ix_user_roles_user_id ON user_roles (user_id);

-- index: ix_users_created_at
CREATE INDEX ix_users_created_at ON users (created_at);

-- index: ix_users_email
CREATE UNIQUE INDEX ix_users_email ON users (email);

-- index: ix_users_nickname
CREATE UNIQUE INDEX ix_users_nickname ON users (nickname);

-- index: ix_users_status
CREATE INDEX ix_users_status ON users (status);

-- index: ix_verify_codes_created_at
CREATE INDEX ix_verify_codes_created_at ON verify_codes (created_at);

-- index: ix_verify_codes_target_scene
CREATE INDEX ix_verify_codes_target_scene ON verify_codes (target, scene);
