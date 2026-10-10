import ProductCatalog from "../components/catalog/ProductCatalog.jsx";
import SiteLayout from "../components/SiteLayout.jsx";

export default function ProductListPage() {
  return (
    <SiteLayout wide>
      <ProductCatalog />
    </SiteLayout>
  );
}
