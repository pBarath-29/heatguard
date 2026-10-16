import "@fontsource-variable/inter";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { EmptyState } from "./components/ui";
import AreaPage from "./pages/AreaPage";
import AskPage from "./pages/AskPage";
import HomePage from "./pages/HomePage";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, retry: 1, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<HomePage />} />
            <Route path="area/:name" element={<AreaPage />} />
            <Route path="ask" element={<AskPage />} />
            {["planner", "now", "my-centre", "proof", "accuracy", "about"].map((p) => <Route key={p} path={p} element={<Navigate to="/" replace />} />)}
            <Route path="*" element={<EmptyState title="Page not found" body="That page doesn't exist." action={<Link className="text-sm font-medium text-brand-700" to="/">Go to my plan</Link>} />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
