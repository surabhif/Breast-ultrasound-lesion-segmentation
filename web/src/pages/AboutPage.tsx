import { SITE } from '../lib/constants'

export default function AboutPage() {
  return (
    <article className="panel prose fade-in">
      <header className="page-intro">
        <h1>About</h1>
        <p>Clinical motivation, dataset citation, method overview, and credits.</p>
      </header>

      <h2>Clinical motivation</h2>
      <p>
        Breast ultrasound is widely used to characterize masses found on mammography or physical
        exam, especially in dense breasts. Segmenting a lesion and estimating whether it looks more
        benign or malignant is a common research task — but published scores on public datasets can
        look better than they are when near-duplicate frames or burned-in caliper marks leak
        information. This demo explores that gap transparently.
      </p>

      <h2>Research demo disclaimer</h2>
      <p>
        <strong>Not for clinical use.</strong> This is an educational high-school research project.
        It must not be used for diagnosis, triage, or screening. Model outputs can be wrong, biased,
        or driven by dataset artifacts.
      </p>

      <h2>Dataset: BUSI</h2>
      <p>
        We use the Breast Ultrasound Images Dataset (BUSI) from Al-Dhabyani et al. (Data in Brief,
        2020): roughly 780 PNG ultrasound images labeled benign, malignant, or normal, each with a
        ground-truth mask (some lesions have multiple mask files that we merge). BUSI does{' '}
        <em>not</em> provide patient IDs, so true patient-level splits are impossible. We instead
        keep perceptual-hash near-duplicate groups together across splits.
      </p>
      <p>
        <strong>Licensing note:</strong> redistribution rights for the full BUSI archive are not
        clearly stated in a machine-readable license. This repository does <em>not</em> commit the
        full dataset; a download script fetches a public Hugging Face mirror. Only a tiny cited
        sample set ships with the web demo.
      </p>

      <h2>What this app does</h2>
      <ul>
        <li>
          An educational tour on breast ultrasound, BUSI labels, segmentation, and data pitfalls.
        </li>
        <li>
          An in-browser detector that predicts a lesion mask overlay and a benign-vs-malignant
          score on BUSI-style ultrasound images.
        </li>
        <li>
          A Results page with Dice, IoU, classification metrics, and the cleaning experiment from
          the current training run.
        </li>
        <li>
          A model card documenting intended use, data, and limitations — educational, not clinical.
        </li>
      </ul>

      <h2>Method (short)</h2>
      <ul>
        <li>U-Net segmentation with an auxiliary benign-vs-malignant head</li>
        <li>Normal images trained with empty masks (“no lesion”)</li>
        <li>Grouped stratified 5-fold CV + held-out test</li>
        <li>Automated audit for calipers / burned-in text and near-duplicates</li>
        <li>Exported ONNX model for fully in-browser inference</li>
      </ul>
      <p>
        For a student-friendly walkthrough of every design choice, see{' '}
        <a href={`${SITE.githubUrl}/blob/main/docs/HOW_IT_WORKS.md`}>docs/HOW_IT_WORKS.md</a>.
      </p>

      <h2 id="cite">How to cite</h2>
      <p>
        Dataset: Al-Dhabyani W, Gomaa M, Khaled H, Fahmy A. Dataset of breast ultrasound images.
        Data in Brief. 2020;28:104863. https://doi.org/10.1016/j.dib.2019.104863
      </p>
      <p>
        This project repository: Surabhi Fadnavis. Breast ultrasound lesion segmentation research
        demo. {SITE.githubUrl}
      </p>

      <h2>Credits</h2>
      <p>
        Project by Surabhi Fadnavis (high-school senior interested in surgical oncology). Web and
        training code structure deliberately mirrors her earlier PatchCamelyon demo. Substantial
        implementation work was done with AI coding assistance (Cursor cloud agent); Surabhi owns
        the research questions, interpretation, and presentation.
      </p>
      <p className="muted tiny">MIT license for code. BUSI images remain under their original terms.</p>
    </article>
  )
}
