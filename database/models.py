from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Float,
    func,
    event,
    Table,
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker
from .base import Base
from bkt.engine import BKTEngine
import uuid

# Section-User association table (many-to-many)
section_users = Table('section_users', Base.metadata,
    Column('section_id', Integer, ForeignKey('sections.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True)
)

# Section-Category association table (many-to-many)
section_categories = Table('section_categories', Base.metadata,
    Column('section_id', Integer, ForeignKey('sections.id'), primary_key=True),
    Column('category_id', Integer, ForeignKey('categories.id'), primary_key=True)
)

# SECTION
class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    uuid = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Many-to-many relationship with users
    users = relationship("User", secondary=section_users, back_populates="sections")
    
    # Many-to-many relationship with categories
    categories = relationship("Category", secondary=section_categories, back_populates="sections")
    
    def __repr__(self):
        return f"<Section(id={self.id}, name='{self.name}')>"

# CATEGORY (Track)
class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    uuid = Column(String, unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Add questions relationship
    questions = relationship("Question", back_populates="category", cascade="all, delete-orphan")
    
    # Add relationship to UserCategory
    user_categories = relationship("UserCategory", back_populates="category", cascade="all, delete-orphan")
    
    # Add relationship to Section (many-to-many)
    sections = relationship("Section", secondary=section_categories, back_populates="categories")

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"

# QUESTION
class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    uuid = Column(String, unique=True, nullable=False)
    
    # Update the relationship to match Category model
    category = relationship("Category", back_populates="questions")
    
    options = relationship(
        "Option", back_populates="question", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Question(id={self.id}, text='{self.text[:30]}...')>"

# OPTION (Answers for Questions)
class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)
    is_correct = Column(Boolean, default=False)

    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    question = relationship("Question", back_populates="options")
    uuid = Column(String, unique=True, nullable=False)

    def __repr__(self):
        return f"<Option(id={self.id}, text='{self.text[:30]}...', is_correct={self.is_correct})>"


# USER (Learner)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)  # For authentication
    is_admin = Column(Boolean, default=False)  # Admin flag

    attempts = relationship(
        "AttemptLog", back_populates="user", cascade="all, delete-orphan"
    )
    user_categories = relationship("UserCategory", back_populates="user", cascade="all, delete-orphan")
    
    # Add relationship to Section (many-to-many)
    sections = relationship("Section", secondary=section_users, back_populates="users")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}')>"

    def get_or_create_category_state(self, category_id: int, session) -> 'UserCategory':
        """Get or create a UserCategory state for a given category."""
        user_category = session.query(UserCategory).filter_by(
            user_id=self.id,
            category_id=category_id
        ).first()
        
        if not user_category:
            user_category = UserCategory(
                user_id=self.id,
                category_id=category_id,
                current_knowledge=0.0,
                p_init=0.0
            )
            session.add(user_category)
            session.commit()
        
        return user_category

    def update_knowledge_state(self, category_id: int, is_correct: bool, session) -> None:
        """Update the knowledge state for a category based on user performance."""
        user_category = self.get_or_create_category_state(category_id, session)
        user_category.update_knowledge_state(is_correct)
        session.commit()

# USER CATEGORY (BKT State per User-Category)
class UserCategory(Base):
    __tablename__ = "user_categories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    
    # BKT parameters with updated defaults for significantly slower learning
    current_knowledge = Column(Float, default=0.0)  # Initial knowledge is now 0
    p_init = Column(Float, default=0.0)  # Initial knowledge prior is now 0
    p_transit = Column(Float, default=0.15)  # Much slower learning rate
    p_slip = Column(Float, default=0.15)  # Higher chance of slipping
    p_guess = Column(Float, default=0.08)  # Lower chance of guessing
    p_lapse = Column(Float, default=0.30)  # Unchanged lapse probability
    consecutive_correct = Column(Integer, default=0)  # Track consecutive correct answers
    
    # Relationships
    user = relationship("User", back_populates="user_categories")
    category = relationship("Category", back_populates="user_categories")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_bkt_engine()

    def _init_bkt_engine(self):
        """Initialize the BKT engine with current parameters"""
        self.bkt_engine = BKTEngine(
            p_init=self.p_init,
            p_transit=self.p_transit,
            p_slip=self.p_slip,
            p_guess=self.p_guess,
            p_lapse=self.p_lapse
        )
        # Set the consecutive correct counter to match the stored value
        self.bkt_engine.consecutive_correct = self.consecutive_correct

    def update_knowledge_state(self, is_correct: bool) -> None:
        """Update the knowledge state using BKT."""
        # First predict the new state
        predicted_knowledge = self.bkt_engine.predict(self.current_knowledge)
        # Then update based on the actual performance
        self.current_knowledge = self.bkt_engine.update(predicted_knowledge, is_correct)
        # Save the consecutive correct counter
        self.consecutive_correct = self.bkt_engine.consecutive_correct
        # Reinitialize BKT engine with updated parameters
        self._init_bkt_engine()

    def is_mastered(self, threshold: float = 0.985) -> bool:
        """Check if the user has mastered this category using a very high threshold."""
        if not hasattr(self, 'bkt_engine'):
            self._init_bkt_engine()
        return self.bkt_engine.is_mastered(self.current_knowledge, threshold)

    def __repr__(self):
        return f"<UserCategory(user_id={self.user_id}, category_id={self.category_id}, knowledge={self.current_knowledge:.2f})>"

# Add event listener to initialize BKT engine when UserCategory is loaded
@event.listens_for(UserCategory, 'load')
def init_bkt_engine(target, context):
    target._init_bkt_engine()

# ATTEMPT LOG (User interactions)
class AttemptLog(Base):
    __tablename__ = "attempt_logs"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    option_id = Column(Integer, ForeignKey("options.id"))

    is_correct = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="attempts")
    question = relationship("Question")
    option = relationship("Option")

    def __repr__(self):
        return (
            f"<AttemptLog(user_id={self.user_id}, question_id={self.question_id}, "
            f"option_id={self.option_id}, is_correct={self.is_correct})>"
        )


# PROGRESS TRACKER (Optional - User progress per category)
class Progress(Base):
    __tablename__ = "progress"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

    # Accuracy as % or score for adaptive learning insights
    accuracy = Column(Float, default=0.0)
    completed = Column(Boolean, default=False)

    user = relationship("User")
    category = relationship("Category")

    def __repr__(self):
        return (
            f"<Progress(user_id={self.user_id}, category_id={self.category_id}, "
            f"accuracy={self.accuracy}, completed={self.completed})>"
        )
