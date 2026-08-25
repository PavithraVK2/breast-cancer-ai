# 🩺 OncoSVM AI — Breast Cancer Classification System

[![Live Demo](https://img.shields.io/badge/Live_Demo-Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://frontend-delta-hazel-33.vercel.app)
[![Accuracy](https://img.shields.io/badge/SVM_Accuracy-98.25%25-success?style=for-the-badge&logo=scikitlearn&logoColor=white)](https://frontend-delta-hazel-33.vercel.app)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React_18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)

> An end-to-end clinical AI diagnostic application designed for automated fine-needle aspirate (FNA) cell nuclei biopsy evaluation using high-dimensional Support Vector Machine (SVM) classifiers.

---

## 🌐 Live Deployed Application

🔗 **Live Website:** [https://frontend-delta-hazel-33.vercel.app](https://frontend-delta-hazel-33.vercel.app)

* **Demo Login:** Google Sign-In (1-click account chooser) or Email / Password.
* **Diagnostics Portal:** [https://frontend-delta-hazel-33.vercel.app/prediction](https://frontend-delta-hazel-33.vercel.app/prediction)

---

## ✨ Key Features

1. **🔬 Wisconsin 30-Feature Diagnostic Engine:**
   - Evaluates full 30 morphological features (Mean, Standard Error, and Worst) across Radius, Texture, Perimeter, Area, Smoothness, Compactness, Concavity, Concave Points, Symmetry, and Fractal Dimension.
2. **⚡ 1-Click Clinical Preset Profiles:**
   - Instant 1-click loading of *Typical Benign*, *Typical Malignant*, *Borderline Indeterminate*, *Dense Non-Cancer*, and *Random Biopsy* cases.
3. **📊 Real-time Tumor Morphology Risk Gauge:**
   - Live visual indicator estimating malignancy risk index as parameters are adjusted.
4. **🧠 Explainable AI & Feature Reasoning:**
   - Highlights the top 5 clinical features driving the SVM hyperplane classification.
5. **🖨️ Clinical Medical PDF Reports & CSV Export:**
   - 1-click print-ready diagnostic summary with compliance statements, patient ID stamps, and confidence margins.
6. **🔐 Google Authentication & Account Chooser:**
   - Integrated Google OAuth account switcher and email registration.

---

## 🏗️ Architecture & Tech Stack

- **Machine Learning:** Scikit-Learn `SVC(kernel='rbf', probability=True)` trained on the Breast Cancer Wisconsin Diagnostic dataset (**98.25% test accuracy**).
- **Backend:** FastAPI, Uvicorn, Motor, Pydantic, Joblib.
- **Frontend:** React 18, Tailwind CSS, Lucide Icons, Recharts, Sonner.
- **Deployment:** Vercel Production.

---

## 🚀 Local Development Setup

### 1. Backend Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python train_model.py
python -m uvicorn server:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install --legacy-peer-deps
npm start
```

---

## 📂 Repository Link

🔗 **GitHub Repository:** [https://github.com/PavithraVK2/breast-cancer-ai](https://github.com/PavithraVK2/breast-cancer-ai)
