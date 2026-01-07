package mysql
package mysql_test

import (
	"context"
	testing "testing"

	"github.com/stretchr/testify/require"

	"github.com/openfga/openfga/pkg/storage/mysql"
	"github.com/openfga/openfga/pkg/storage/sqlcommon"
	storagefixtures "github.com/openfga/openfga/pkg/testfixtures/storage"
)

// Basic readiness check to ensure MariaDB test container and migrations run correctly.
func TestMariaDBDatastoreIsReady(t *testing.T) {
	testDatastore := storagefixtures.RunDatastoreTestContainer(t, "mariadb")
	uri := testDatastore.GetConnectionURI(true)

	ds, err := mysql.New(uri, sqlcommon.NewConfig())
	require.NoError(t, err)
	t.Cleanup(ds.Close)

	status, err := ds.IsReady(context.Background())
	require.NoError(t, err)
	require.True(t, status.IsReady)
}
