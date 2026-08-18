use movies;

CREATE TABLE Movies(
	movie_id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(255) NOT NULL,
    release_year YEAR NOT NULL,
    genre VARCHAR(100) NOT NULL,
    language VARCHAR(50) DEFAULT 'Telugu',
    duration_minutes INT NOT NULL,
    rating DECIMAL(3,1),
    director_id INT,
    FOREIGN KEY (director_id) REFERENCES Directors(director_id)
    );
    
CREATE TABLE Directors(
	director_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    dob DATE,
    nationality VARCHAR(100),
    awards TEXT
);


CREATE TABLE Actors(
	actor_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    dob DATE,
    gender CHAR(1),
    nationality VARCHAR(100),
    debut_year YEAR
    );
    
    
CREATE TABLE Movie_Cast(
	movie_id INT,
    actor_id INT,
    role_name VARCHAR(255),
    screen_time_minutes INT,
    FOREIGN KEY (movie_id) REFERENCES Movies(movie_id),
    FOREIGN KEY (actor_id) REFERENCES Actors(actor_id),
    PRIMARY KEY (movie_id, actor_id)
    );
    

CREATE TABLE Box_office(
	movie_id INT,
    actor_id INT,
    role_name VARCHAR(255),
    screen_time_minutes INT,
    FOREIGN KEY (movie_id) REFERENCES Movies(movie_id),
    FOREIGN KEY (actor_id) REFERENCES Actors(actor_id),
    PRIMARY KEY (movie_id, actor_id)
    );
    
CREATE TABLE Box_Office(
	movie_id INT,
    budget BIGINT,
    box_office_collection BIGINT,
    domestic_collection BIGINT,
    international_collection BIGINT,
    FOREIGN KEY (movie_id) REFERENCES Movies (movie_id),
    PRIMARY KEY (movie_id)
    );
    
    
    
    
    
    
    
    