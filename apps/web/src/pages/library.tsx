import WorkbenchApp from "@/components/WorkbenchApp";

export default function LibraryRoute() {
  return <WorkbenchApp initialWorkspace="library" />;
}

export async function getServerSideProps() {
  return { props: {} };
}
