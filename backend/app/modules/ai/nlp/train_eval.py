"""
AegisAI NLP Disaster Classifier — 2,500+ Corpus Training and Holdout Evaluation.

Performs 80/20 stratified train/test split on 2,700 diverse disaster samples across 9 classes.
Reports exact Precision, Recall, and F1-Score per class.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split

from app.modules.ai.nlp.classifier import DISASTER_CLASSES
from app.modules.ai.nlp.corpus import get_expanded_corpus


def train_and_evaluate(samples_per_class: int = 300, random_state: int = 42):
    corpus = get_expanded_corpus(samples_per_class=samples_per_class, seed=random_state)
    texts = [item[0] for item in corpus]
    labels = [item[1] for item in corpus]

    print(f"Total Corpus Size: {len(corpus)} samples across {len(DISASTER_CLASSES)} classes.")

    # 80/20 stratified split
    X_train, X_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=0.20,
        random_state=random_state,
        stratify=labels,
    )

    print(f"Training set: {len(X_train)} samples | Test holdout: {len(X_test)} samples")

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=5000,
        sublinear_tf=True,
        stop_words="english",
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    clf = LogisticRegression(
        C=3.0,
        class_weight="balanced",
        max_iter=500,
        random_state=random_state,
    )
    clf.fit(X_train_vec, y_train)

    y_pred = clf.predict(X_test_vec)
    acc = accuracy_score(y_test, y_pred)

    report_dict = classification_report(
        y_test,
        y_pred,
        labels=DISASTER_CLASSES,
        target_names=DISASTER_CLASSES,
        output_dict=True,
    )
    report_text = classification_report(
        y_test,
        y_pred,
        labels=DISASTER_CLASSES,
        target_names=DISASTER_CLASSES,
        digits=4,
    )

    print("\n================ NLP EVALUATION REPORT (80/20 Holdout) ================")
    print(f"Overall Accuracy: {acc * 100:.2f}%\n")
    print(report_text)
    print("=======================================================================\n")

    return {
        "accuracy": acc,
        "report_dict": report_dict,
        "vectorizer": vectorizer,
        "model": clf,
    }


if __name__ == "__main__":
    train_and_evaluate()
