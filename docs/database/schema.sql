-- 브루밍 카페 예약·문의·홍보 시스템 데이터베이스 (SQLite)
-- 자동 생성: python -m scripts.export_database
-- 직접 고치지 말고 모델·가상 데이터를 고친 뒤 다시 생성한다.
-- 테이블 8개

CREATE TABLE customers (
	id INTEGER NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	phone VARCHAR(30) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE stores (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	address VARCHAR(200) NOT NULL, 
	open_time TIME NOT NULL, 
	close_time TIME NOT NULL, 
	closed_days VARCHAR(50) NOT NULL, 
	phone VARCHAR(30) NOT NULL, 
	capacity_per_hour INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE faqs (
	id INTEGER NOT NULL, 
	store_id INTEGER NOT NULL, 
	question VARCHAR(300) NOT NULL, 
	answer TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id)
);

CREATE TABLE inquiries (
	id INTEGER NOT NULL, 
	store_id INTEGER NOT NULL, 
	customer_id INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	received_at DATETIME NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	ai_draft TEXT, 
	final_answer TEXT, 
	check_result TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);

CREATE TABLE marketing_contents (
	id INTEGER NOT NULL, 
	store_id INTEGER NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	target VARCHAR(100) NOT NULL, 
	keywords VARCHAR(200) NOT NULL, 
	text TEXT NOT NULL, 
	check_result TEXT, 
	saved_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id)
);

CREATE TABLE menu_items (
	id INTEGER NOT NULL, 
	store_id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	price INTEGER NOT NULL, 
	description VARCHAR(300) NOT NULL, 
	on_sale BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id)
);

CREATE TABLE reservations (
	id INTEGER NOT NULL, 
	store_id INTEGER NOT NULL, 
	customer_id INTEGER NOT NULL, 
	reserved_at DATETIME NOT NULL, 
	party_size INTEGER NOT NULL, 
	request VARCHAR(300) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(store_id) REFERENCES stores (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);

CREATE TABLE reservation_histories (
	id INTEGER NOT NULL, 
	reservation_id INTEGER NOT NULL, 
	from_status VARCHAR(10) NOT NULL, 
	to_status VARCHAR(10) NOT NULL, 
	changed_at DATETIME NOT NULL, 
	memo VARCHAR(100), 
	PRIMARY KEY (id), 
	FOREIGN KEY(reservation_id) REFERENCES reservations (id)
);
