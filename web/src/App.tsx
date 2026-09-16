import { AppShell, EmptyState } from "./components";
import { navigate, usePath } from "./hooks";
import { DatasetDetailPage } from "./pages/DatasetDetailPage";
import { DatasetsPage } from "./pages/DatasetsPage";
import { ExperimentDetailPage } from "./pages/ExperimentDetailPage";
import { ExperimentsPage } from "./pages/ExperimentsPage";
import { HypothesesPage } from "./pages/HypothesesPage";
import { HypothesisDetailPage } from "./pages/HypothesisDetailPage";
import { NewExperimentPage } from "./pages/NewExperimentPage";
import { NewDatasetPage } from "./pages/NewDatasetPage";
import { NewHypothesisPage } from "./pages/NewHypothesisPage";
import { OverviewPage } from "./pages/OverviewPage";
import { ArchivePage } from "./pages/ArchivePage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  const fullPath = usePath();
  const path = fullPath.split("?")[0];
  let page: React.ReactNode;

  if (path === "/") page = <OverviewPage />;
  else if (path === "/hypotheses") page = <HypothesesPage />;
  else if (path === "/datasets") page = <DatasetsPage />;
  else if (path === "/datasets/new") page = <NewDatasetPage />;
  else if (path.startsWith("/datasets/")) {
    page = <DatasetDetailPage name={decodeURIComponent(path.split("/")[2] || "")} />;
  }
  else if (path === "/hypotheses/new") page = <NewHypothesisPage />;
  else if (path.startsWith("/hypotheses/")) {
    page = <HypothesisDetailPage id={decodeURIComponent(path.split("/")[2] || "")} />;
  }
  else if (path === "/experiments") page = <ExperimentsPage />;
  else if (path === "/experiments/new") page = <NewExperimentPage />;
  else if (path.startsWith("/experiments/")) {
    page = <ExperimentDetailPage id={decodeURIComponent(path.split("/")[2] || "")} />;
  } else if (path === "/archive") page = <ArchivePage />;
  else if (path === "/settings") page = <SettingsPage />;
  else {
    page = (
      <EmptyState
        title="This view does not exist"
        description="Return to the workspace overview."
        action={
          <button className="button primary" onClick={() => navigate("/")}>
            Go to overview
          </button>
        }
      />
    );
  }

  return <AppShell path={path}>{page}</AppShell>;
}
