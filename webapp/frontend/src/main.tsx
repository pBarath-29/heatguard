import "@fontsource-variable/inter";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { EmptyState } from "./components/ui";
import AboutPage from "./pages/AboutPage";
import AccuracyPage from "./pages/AccuracyPage";
import AreaPage from "./pages/AreaPage";
import AskPage from "./pages/AskPage";
import CheckinPage from "./pages/CheckinPage";
import MyCentrePage from "./pages/MyCentrePage";
import NowPage from "./pages/NowPage";
import ProofPage from "./pages/ProofPage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, retry: 1, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<CheckinPage />} />
            <Route path="area/:name" element={<AreaPage />} />
            <Route path="now" element={<NowPage />} />
            <Route path="my-centre" element={<MyCentrePage />} />
            <Route path="proof" element={<ProofPage />} />
            <Route path="ask" element={<AskPage />} />
            <Route path="accuracy" element={<AccuracyPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="*" element={<EmptyState title="Page not found" body="That page doesn't exist." action={<Link className="text-sm font-medium text-brand-700" to="/">Go to the check-in list</Link>} />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
